"""
Admin API Routes — Protected endpoints for the HR dashboard.

All routes require a valid admin API key passed via X-Admin-Key header
or a valid Supabase Auth token for an admin_users row.

Endpoints:
    GET  /api/admin/candidates              — List all candidates with latest interview + score
    GET  /api/admin/candidates/{id}         — Single candidate detail with full transcript
    POST /api/admin/score/{interview_id}    — Manually trigger scoring for an interview
    GET  /api/admin/dashboard/stats         — Aggregate stats for the dashboard header
"""

import io
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, Header, Depends, UploadFile
from pydantic import BaseModel

try:
    import openpyxl
    _OPENPYXL_AVAILABLE = True
except ImportError:
    _OPENPYXL_AVAILABLE = False

try:
    import csv as _csv_module
except ImportError:
    _csv_module = None

from app.db.supabase_client import get_supabase_client

router = APIRouter()
logger = logging.getLogger(__name__)


# ─── Auth Guard ──────────────────────────────────────────────────────────────

async def verify_admin(
    x_admin_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
) -> dict:
    """
    Verify that the request comes from an authorized admin.

    Supports two auth methods:
    1. X-Admin-Key header — simple shared secret (good for dev / internal tools)
    2. Authorization: Bearer <token> — Supabase Auth JWT (for production dashboard)

    Returns the admin user dict on success, raises 401/403 on failure.
    """
    supabase = get_supabase_client()

    # Method 1: Shared API key (for dev/internal use)
    import os
    admin_api_key = os.getenv("ADMIN_API_KEY")
    logger.info(
        "🔐 Auth check: x_admin_key=%s, env_key=%s, match=%s",
        repr(x_admin_key), repr(admin_api_key),
        x_admin_key == admin_api_key if (x_admin_key and admin_api_key) else "missing"
    )
    if x_admin_key and admin_api_key and x_admin_key == admin_api_key:
        return {"email": "api-key-admin", "role": "super_admin", "full_name": "API Key Admin"}

    # Method 2: Supabase Auth token → look up admin_users table
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        try:
            # Verify the JWT and get user info
            # Note: In production, use supabase.auth.get_user(token)
            # For now, we decode the email from the token and check admin_users
            user_response = supabase.auth.get_user(token)
            if not user_response or not user_response.user:
                raise HTTPException(status_code=401, detail="Invalid auth token")

            user_email = user_response.user.email
            auth_user_id = user_response.user.id

            # Check admin_users table
            result = (
                supabase.table("admin_users")
                .select("*")
                .eq("auth_user_id", str(auth_user_id))
                .eq("is_active", True)
                .execute()
            )

            if not result.data:
                # Try by email as fallback
                result = (
                    supabase.table("admin_users")
                    .select("*")
                    .eq("email", user_email)
                    .eq("is_active", True)
                    .execute()
                )

            if not result.data:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to access the admin dashboard"
                )

            return result.data[0]

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Auth verification failed: %s", e)
            raise HTTPException(status_code=401, detail="Authentication failed")

    raise HTTPException(
        status_code=401,
        detail="Missing authentication. Provide X-Admin-Key header or Authorization: Bearer <token>"
    )


# ─── Candidates List ────────────────────────────────────────────────────────

@router.get("/candidates")
async def list_candidates(
    search: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 50,
    offset: int = 0,
    admin: dict = Depends(verify_admin),
):
    """
    List all candidates with their latest interview and score data.
    Uses LIVE queries for fresh data. Falls back to materialized view if errors.
    """
    try:
        supabase = get_supabase_client()

        # Normalize sort field for ALL paths
        safe_sort = sort_by
        if sort_by in ("candidate_created_at", "interview_created_at"):
            safe_sort = "created_at"

        # ─── LIVE QUERY (always fresh) ──────────────────────────────
        try:
            query = supabase.table("candidates").select("*")

            if search:
                query = query.or_(
                    f"full_name.ilike.%{search}%,"
                    f"target_role.ilike.%{search}%"
                )

            desc = sort_order.lower() == "desc"
            query = query.order(safe_sort, desc=desc)
            query = query.range(offset, offset + limit - 1)

            result = query.execute()
            candidates = result.data or []

            logger.info("📋 Live query returned %d candidates", len(candidates))

            # Enrich each candidate with latest interview + score
            # Each enrichment is individually wrapped to prevent one bad row
            # from killing the entire response
            enriched = []
            for c in candidates:
                cid = c["id"]
                interview = None
                score = None

                try:
                    int_result = (
                        supabase.table("interviews")
                        .select("id, status, created_at, completed_at, "
                                "duration_seconds, is_completed, audio_public_url")
                        .eq("candidate_id", cid)
                        .order("created_at", desc=True)
                        .limit(1)
                        .execute()
                    )
                    interview = int_result.data[0] if int_result.data else None
                except Exception as int_err:
                    logger.warning("Failed to fetch interview for %s: %s", cid, int_err)

                if interview:
                    try:
                        score_result = (
                            supabase.table("scores")
                            .select("final_score, ai_score, hire_recommendation, "
                                    "hire_confidence, bottom_line_summary")
                            .eq("interview_id", interview["id"])
                            .order("scored_at", desc=True)
                            .limit(1)
                            .execute()
                        )
                        score = score_result.data[0] if score_result.data else None
                    except Exception as score_err:
                        logger.warning("Failed to fetch score for interview %s: %s",
                                       interview["id"], score_err)

                enriched.append({
                    **c,
                    "interview": interview,
                    "score": score,
                })

            # Background: refresh MV (non-critical)
            try:
                supabase.rpc('refresh_admin_dashboard').execute()
            except Exception:
                pass

            return {
                "candidates": enriched,
                "total": len(enriched),
                "offset": offset,
                "limit": limit,
                "source": "live_query",
            }

        except Exception as live_err:
            logger.warning("Live query failed, falling back to MV: %s", live_err)

        # ─── FALLBACK: Materialized View ────────────────────────────
        try:
            query = supabase.table("mv_admin_dashboard").select("*")

            if search:
                query = query.or_(
                    f"full_name.ilike.%{search}%,"
                    f"target_role.ilike.%{search}%"
                )

            if status:
                query = query.eq("interview_status", status)

            desc = sort_order.lower() == "desc"
            # Use safe_sort (already normalized above)
            query = query.order(safe_sort, desc=desc)
            query = query.range(offset, offset + limit - 1)

            result = query.execute()
            logger.info("📋 MV fallback returned %d rows", len(result.data or []))

            return {
                "candidates": result.data or [],
                "total": len(result.data or []),
                "offset": offset,
                "limit": limit,
                "source": "materialized_view",
            }
        except Exception as mv_err:
            logger.error("MV fallback also failed: %s", mv_err)
            raise HTTPException(status_code=500, detail=f"Both live and MV queries failed: {mv_err}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error listing candidates: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Candidate Detail ───────────────────────────────────────────────────────

@router.get("/candidates/{candidate_id}")
async def get_candidate_detail(
    candidate_id: str,
    admin: dict = Depends(verify_admin),
):
    """
    Get full candidate detail with interview transcript, score breakdown,
    and audio URL.
    """
    try:
        supabase = get_supabase_client()

        # 1. Fetch candidate
        c_result = (
            supabase.table("candidates")
            .select("*")
            .eq("id", candidate_id)
            .execute()
        )
        if not c_result.data:
            raise HTTPException(status_code=404, detail="Candidate not found")

        candidate = c_result.data[0]

        # 2. Fetch latest interview with full transcript
        i_result = (
            supabase.table("interviews")
            .select("*")
            .eq("candidate_id", candidate_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        interview = i_result.data[0] if i_result.data else None

        # 3. Fetch score for this interview
        score = None
        if interview:
            s_result = (
                supabase.table("scores")
                .select("*")
                .eq("interview_id", interview["id"])
                .order("scored_at", desc=True)
                .limit(1)
                .execute()
            )
            score = s_result.data[0] if s_result.data else None

        # 4. Check if scoring job exists / is in progress
        scoring_job = None
        if interview:
            try:
                sj_result = (
                    supabase.table("scoring_jobs")
                    .select("*")
                    .eq("interview_id", interview["id"])
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                scoring_job = sj_result.data[0] if sj_result.data else None
            except Exception as sj_err:
                logger.warning("Failed to fetch scoring_job: %s", sj_err)

        # 5. Auto-mark as "viewed" if currently "new"
        if interview and interview.get("review_status") == "new":
            try:
                _reviewer_id = admin.get("auth_user_id") or admin.get("id")
                _auto_update = {
                    "review_status": "viewed",
                    "reviewed_at": datetime.utcnow().isoformat(),
                }
                if _reviewer_id:
                    _auto_update["reviewed_by"] = _reviewer_id
                supabase.table("interviews").update(_auto_update).eq("id", interview["id"]).execute()
                interview["review_status"] = "viewed"
                logger.info("👁️ Auto-marked interview %s as viewed", interview["id"])
            except Exception as view_err:
                logger.warning("Failed to auto-mark as viewed: %s", view_err)

        return {
            "candidate": candidate,
            "interview": interview,
            "score": score,
            "scoring_job": scoring_job,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching candidate %s: %s", candidate_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── HR Review Status Update ────────────────────────────────────────────────

VALID_REVIEW_STATUSES = [
    "new", "viewed", "strong_candidate", "weak_candidate",
    "shortlisted", "hired", "rejected",
]


class ReviewStatusUpdate(BaseModel):
    review_status: str
    hr_notes: Optional[str] = None


@router.patch("/candidates/{candidate_id}/review")
async def update_review_status(
    candidate_id: str,
    body: ReviewStatusUpdate,
    admin: dict = Depends(verify_admin),
):
    """
    Update the HR review status for a candidate's latest interview.
    This is the core decision-making endpoint for the Qabalan HR workflow.

    Status flow:
        new → viewed → strong_candidate / weak_candidate → shortlisted → hired / rejected
    """
    if body.review_status not in VALID_REVIEW_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid review_status. Must be one of: {VALID_REVIEW_STATUSES}"
        )

    try:
        supabase = get_supabase_client()

        # Find latest interview for this candidate
        i_result = (
            supabase.table("interviews")
            .select("id, status, review_status")
            .eq("candidate_id", candidate_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if not i_result.data:
            raise HTTPException(
                status_code=404,
                detail="No interview found for this candidate"
            )

        interview_id = i_result.data[0]["id"]
        old_status = i_result.data[0].get("review_status", "new")

        # Build update payload
        reviewer_id = admin.get("auth_user_id") or admin.get("id")
        update_data = {
            "review_status": body.review_status,
            "reviewed_at": datetime.utcnow().isoformat(),
        }
        if reviewer_id:
            update_data["reviewed_by"] = reviewer_id

        if body.hr_notes is not None:
            update_data["hr_notes"] = body.hr_notes

        # Execute update
        supabase.table("interviews").update(
            update_data
        ).eq("id", interview_id).execute()

        logger.info(
            "📋 Review status updated: %s → %s (candidate: %s, by: %s)",
            old_status, body.review_status, candidate_id,
            admin.get("email", "unknown"),
        )

        return {
            "status": "updated",
            "interview_id": interview_id,
            "old_review_status": old_status,
            "new_review_status": body.review_status,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating review status: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Manual Scoring Trigger ─────────────────────────────────────────────────

class ManualScoreRequest(BaseModel):
    force: bool = False  # If True, re-score even if a score already exists


@router.post("/score/{interview_id}")
async def trigger_manual_scoring(
    interview_id: str,
    body: ManualScoreRequest = ManualScoreRequest(),
    admin: dict = Depends(verify_admin),
):
    """
    Manually trigger scoring for a specific interview.
    Creates a scoring_jobs row for the background worker to pick up.
    """
    try:
        supabase = get_supabase_client()

        # Verify interview exists
        i_result = (
            supabase.table("interviews")
            .select("id, candidate_id, status")
            .eq("id", interview_id)
            .execute()
        )
        if not i_result.data:
            raise HTTPException(status_code=404, detail="Interview not found")

        interview = i_result.data[0]
        candidate_id = interview["candidate_id"]

        # Check if score already exists (unless force=True)
        if not body.force:
            existing = (
                supabase.table("scores")
                .select("id")
                .eq("interview_id", interview_id)
                .execute()
            )
            if existing.data:
                return {
                    "status": "already_scored",
                    "message": "This interview already has a score. Set force=true to re-score.",
                    "score_id": existing.data[0]["id"],
                }

        # Check if a pending/processing job already exists
        pending = (
            supabase.table("scoring_jobs")
            .select("id, status")
            .eq("interview_id", interview_id)
            .in_("status", ["pending", "processing"])
            .execute()
        )
        if pending.data:
            return {
                "status": "job_in_progress",
                "message": "A scoring job is already queued or processing.",
                "job_id": pending.data[0]["id"],
                "job_status": pending.data[0]["status"],
            }

        # Create new scoring job
        job_result = supabase.table("scoring_jobs").insert({
            "interview_id": interview_id,
            "candidate_id": candidate_id,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }).execute()

        job_id = job_result.data[0]["id"] if job_result.data else "unknown"

        logger.info(
            "Manual scoring triggered by %s for interview %s (job: %s)",
            admin.get("email", "unknown"), interview_id, job_id,
        )

        return {
            "status": "queued",
            "message": "Scoring job created. The background worker will process it shortly.",
            "job_id": job_id,
            "interview_id": interview_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error triggering manual scoring: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Dashboard Stats ────────────────────────────────────────────────────────

@router.get("/dashboard/stats")
async def get_dashboard_stats(
    admin: dict = Depends(verify_admin),
):
    """
    Aggregate statistics for the admin dashboard header.
    Uses direct data fetches (not count="exact") for maximum reliability.
    """
    try:
        supabase = get_supabase_client()

        # Total candidates — fetch IDs only, count via len()
        candidates_result = supabase.table("candidates").select("id").execute()
        total_candidates = len(candidates_result.data) if candidates_result.data else 0

        # Total interviews
        interviews_result = supabase.table("interviews").select("id").execute()
        total_interviews = len(interviews_result.data) if interviews_result.data else 0

        # Completed interviews — check BOTH status and is_completed flag
        completed_result = (
            supabase.table("interviews")
            .select("id")
            .or_("status.eq.completed,is_completed.eq.true")
            .execute()
        )
        completed_interviews = len(completed_result.data) if completed_result.data else 0

        # Average score
        scores_result = supabase.table("scores").select("final_score").execute()
        scores = scores_result.data or []
        valid_scores = [s["final_score"] for s in scores if s.get("final_score") is not None]
        avg_score = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else 0

        # Hire rate (% recommended)
        hire_result = supabase.table("scores").select("hire_recommendation").execute()
        hire_data = hire_result.data or []
        hire_yes = sum(1 for h in hire_data if h.get("hire_recommendation") in [True, "yes", "YES"])
        hire_rate = round((hire_yes / len(hire_data)) * 100, 1) if hire_data else 0

        # Pending scoring jobs
        pending_result = (
            supabase.table("scoring_jobs")
            .select("id")
            .eq("status", "pending")
            .execute()
        )
        pending_jobs = len(pending_result.data) if pending_result.data else 0

        logger.info(
            "📊 Stats: candidates=%d, interviews=%d, completed=%d, avg_score=%.1f",
            total_candidates, total_interviews, completed_interviews, avg_score,
        )

        return {
            "total_candidates": total_candidates,
            "total_interviews": total_interviews,
            "completed_interviews": completed_interviews,
            "average_score": avg_score,
            "hire_rate": hire_rate,
            "pending_scoring_jobs": pending_jobs,
        }

    except Exception as e:
        logger.error("Error fetching dashboard stats: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Reports Aggregation ────────────────────────────────────────────────────

@router.get("/dashboard/reports")
async def get_dashboard_reports(
    admin: dict = Depends(verify_admin),
):
    """
    Aggregated data for the Reports page charts:
    1. Score Distribution (histogram buckets)
    2. Candidates by Role (pie chart)
    3. Hiring Funnel (registered → interviewed → scored → hired)
    4. Daily application trend
    """
    try:
        supabase = get_supabase_client()

        # ── 1. Score Distribution ─────────────────────────
        scores_result = supabase.table("scores").select("final_score").execute()
        scores = [s["final_score"] for s in (scores_result.data or []) if s.get("final_score") is not None]

        buckets = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
        for s in scores:
            if s <= 20: buckets["0-20"] += 1
            elif s <= 40: buckets["21-40"] += 1
            elif s <= 60: buckets["41-60"] += 1
            elif s <= 80: buckets["61-80"] += 1
            else: buckets["81-100"] += 1

        score_distribution = [{"range": k, "count": v} for k, v in buckets.items()]

        # ── 2. Candidates by Role ─────────────────────────
        candidates_result = supabase.table("candidates").select("target_role").execute()
        role_counts: dict = {}
        for c in (candidates_result.data or []):
            role = c.get("target_role") or "غير محدد"
            role_counts[role] = role_counts.get(role, 0) + 1

        role_breakdown = [{"role": k, "count": v} for k, v in role_counts.items()]

        # ── 3. Hiring Funnel ──────────────────────────────
        total_candidates = len(candidates_result.data or [])

        interviews_result = supabase.table("interviews").select("id").execute()
        total_interviewed = len(interviews_result.data or [])

        total_scored = len(scores)

        # Count hired
        hired_result = (
            supabase.table("interviews")
            .select("id")
            .eq("review_status", "hired")
            .execute()
        )
        total_hired = len(hired_result.data or [])

        funnel = [
            {"stage": "مسجل", "stageEn": "Registered", "count": total_candidates},
            {"stage": "مقابلة", "stageEn": "Interviewed", "count": total_interviewed},
            {"stage": "مُقيّم", "stageEn": "Scored", "count": total_scored},
            {"stage": "موظف", "stageEn": "Hired", "count": total_hired},
        ]

        # ── 4. Daily Application Trend (last 30 days) ────
        from datetime import timedelta
        thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()

        daily_result = (
            supabase.table("candidates")
            .select("created_at")
            .gte("created_at", thirty_days_ago)
            .order("created_at")
            .execute()
        )

        daily_counts: dict = {}
        for c in (daily_result.data or []):
            day = c["created_at"][:10]  # YYYY-MM-DD
            daily_counts[day] = daily_counts.get(day, 0) + 1

        daily_trend = [{"date": k, "count": v} for k, v in sorted(daily_counts.items())]

        # ── 5. Review Status Distribution ─────────────────
        review_result = supabase.table("interviews").select("review_status").execute()
        review_counts: dict = {}
        for r in (review_result.data or []):
            status = r.get("review_status") or "new"
            review_counts[status] = review_counts.get(status, 0) + 1

        review_distribution = [{"status": k, "count": v} for k, v in review_counts.items()]

        return {
            "score_distribution": score_distribution,
            "role_breakdown": role_breakdown,
            "funnel": funnel,
            "daily_trend": daily_trend,
            "review_distribution": review_distribution,
        }

    except Exception as e:
        logger.error("Error fetching reports: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Question Bank CRUD ─────────────────────────────────────────────────────

@router.get("/questions")
async def list_questions(
    admin: dict = Depends(verify_admin),
):
    """List all questions from question_bank, grouped by category."""
    try:
        supabase = get_supabase_client()
        result = supabase.table("question_bank").select("*").order("category_id").order("display_order").execute()
        questions = result.data or []

        # Group by category
        categories: dict = {}
        for q in questions:
            cat_id = q.get("category_id", 0)
            if cat_id not in categories:
                categories[cat_id] = {
                    "category_id": cat_id,
                    "category_name_ar": q.get("category_name_ar", ""),
                    "category_name_en": q.get("category_name_en", ""),
                    "questions": [],
                }
            categories[cat_id]["questions"].append(q)

        return {
            "categories": list(categories.values()),
            "total_questions": len(questions),
        }

    except Exception as e:
        logger.error("Error listing questions: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class QuestionUpdate(BaseModel):
    question_text_ar: Optional[str] = None
    question_text_en: Optional[str] = None
    weight: Optional[float] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


@router.patch("/questions/{question_id}")
async def update_question(
    question_id: str,
    body: QuestionUpdate,
    admin: dict = Depends(verify_admin),
):
    """Update a question's text, weight, or active status."""
    try:
        supabase = get_supabase_client()

        update_data = {k: v for k, v in body.dict().items() if v is not None}
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        supabase.table("question_bank").update(update_data).eq("question_id", question_id).execute()

        logger.info("Question %s updated by %s: %s", question_id, admin.get("email"), update_data)
        return {"status": "updated", "question_id": question_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating question: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class QuestionCreate(BaseModel):
    category_id: int
    category_name_ar: str
    category_name_en: str = ""
    category_stage: str = "general"
    question_text_ar: str
    question_text_en: str = ""
    weight: float = 1.0
    is_active: bool = True
    display_order: int = 99


@router.post("/questions")
async def create_question(
    body: QuestionCreate,
    admin: dict = Depends(verify_admin),
):
    """Add a new question to the question bank."""
    try:
        supabase = get_supabase_client()

        # Generate question_id like "q{category}_{n}"
        existing = (
            supabase.table("question_bank")
            .select("question_id")
            .eq("category_id", body.category_id)
            .execute()
        )
        next_num = len(existing.data or []) + 1
        new_qid = f"q{body.category_id}_{next_num}"

        insert_data = body.dict()
        insert_data["question_id"] = new_qid

        result = supabase.table("question_bank").insert(insert_data).execute()

        logger.info("Question %s created by %s", new_qid, admin.get("email"))
        return {"status": "created", "question": result.data[0] if result.data else insert_data}

    except Exception as e:
        logger.error("Error creating question: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/questions/{question_id}")
async def delete_question(
    question_id: str,
    admin: dict = Depends(verify_admin),
):
    """Soft-delete a question by marking it inactive."""
    try:
        supabase = get_supabase_client()
        supabase.table("question_bank").update({"is_active": False}).eq("question_id", question_id).execute()

        logger.info("Question %s deactivated by %s", question_id, admin.get("email"))
        return {"status": "deactivated", "question_id": question_id}

    except Exception as e:
        logger.error("Error deleting question: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Signed Audio URL ────────────────────────────────────────────────────────

AUDIO_STORAGE_BUCKET = "interview-audio"
SIGNED_URL_EXPIRES = 3600  # 1 hour


@router.get("/candidates/{candidate_id}/audio-url")
async def get_audio_signed_url(
    candidate_id: str,
    interview_id: Optional[str] = None,
    admin: dict = Depends(verify_admin),
):
    """
    Return a short-lived signed URL for the interview audio recording.
    Falls back to audio_public_url when no storage path is recorded.
    """
    try:
        supabase = get_supabase_client()

        # Resolve interview
        query = (
            supabase.table("interviews")
            .select("id, audio_storage_path, audio_public_url")
            .eq("candidate_id", candidate_id)
            .order("created_at", desc=True)
            .limit(1)
        )
        if interview_id:
            query = (
                supabase.table("interviews")
                .select("id, audio_storage_path, audio_public_url")
                .eq("id", interview_id)
                .limit(1)
            )

        result = query.execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="No interview found")

        interview = result.data[0]
        storage_path: Optional[str] = interview.get("audio_storage_path")
        public_url: Optional[str] = interview.get("audio_public_url")

        if not storage_path:
            # No stored path — return whatever public URL exists (may be None)
            return {
                "signed_url": public_url,
                "fallback": True,
                "storage_path": None,
            }

        # Generate signed URL via Supabase Storage
        signed = supabase.storage.from_(AUDIO_STORAGE_BUCKET).create_signed_url(
            storage_path, SIGNED_URL_EXPIRES
        )

        # supabase-py returns {"signedURL": "..."} or {"error": "..."}
        signed_url = signed.get("signedURL") or signed.get("signed_url") or signed.get("signedUrl")
        if not signed_url:
            logger.warning("Signed URL generation returned unexpected shape: %s", signed)
            return {"signed_url": public_url, "fallback": True, "storage_path": storage_path}

        logger.info("Generated signed URL for interview %s (expires in %ds)", interview["id"], SIGNED_URL_EXPIRES)
        return {
            "signed_url": signed_url,
            "expires_in_seconds": SIGNED_URL_EXPIRES,
            "storage_path": storage_path,
            "fallback": False,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error generating signed URL for candidate %s: %s", candidate_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Candidate Column Map (Excel / CSV import) ───────────────────────────────

_IMPORT_COLUMN_MAP = {
    # Arabic headers
    "الاسم الكامل": "full_name",
    "الاسم": "full_name",
    "رقم الهاتف": "phone_number",
    "الهاتف": "phone_number",
    "الوظيفة المطلوبة": "target_role",
    "الوظيفة": "target_role",
    "سنوات الخبرة": "years_of_experience",
    "الخبرة": "years_of_experience",
    "الراتب المتوقع": "expected_salary",
    "الراتب": "expected_salary",
    "العنوان": "detailed_residence",
    "المنطقة السكنية": "detailed_residence",
    "الجنس": "gender",
    "تاريخ الميلاد": "date_of_birth",
    "الجنسية": "nationality",
    "الحالة الاجتماعية": "marital_status",
    "الفئة العمرية": "age_range",
    "المسار الدراسي": "academic_status",
    "المؤهل الأكاديمي": "academic_qualification",
    "قرب السكن": "proximity_to_branch",
    "أقارب بالشركة": "has_relatives_at_company",
    "عمل سابق بقبلان": "previously_at_qabalan",
    "ضمان اجتماعي": "social_security_issues",
    "الصلاة": "prayer_regularity",
    "التدخين": "is_smoker",
    "مانع حلاقة": "grooming_objection",
    "البدء فوراً": "can_start_immediately",
    "الوردية": "preferred_schedule",
    "خبرة ميدانية": "has_field_experience",
    # English headers (fallback)
    "full_name": "full_name",
    "phone_number": "phone_number",
    "phone": "phone_number",
    "target_role": "target_role",
    "years_of_experience": "years_of_experience",
    "expected_salary": "expected_salary",
    "detailed_residence": "detailed_residence",
    "gender": "gender",
}

REQUIRED_IMPORT_FIELDS = {"full_name", "phone_number"}


def _parse_excel_rows(file_bytes: bytes) -> List[dict]:
    """Parse .xlsx bytes → list of dicts with mapped keys."""
    if not _OPENPYXL_AVAILABLE:
        raise RuntimeError("openpyxl is not installed. Run: pip install openpyxl")
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    raw_headers = [str(h).strip() if h is not None else "" for h in rows[0]]
    mapped_headers = [_IMPORT_COLUMN_MAP.get(h, None) for h in raw_headers]
    result = []
    for row in rows[1:]:
        if all(v is None or v == "" for v in row):
            continue
        record = {}
        for col_idx, db_col in enumerate(mapped_headers):
            if db_col and col_idx < len(row):
                val = row[col_idx]
                if val is not None:
                    record[db_col] = str(val).strip()
        result.append(record)
    return result


def _parse_csv_rows(file_bytes: bytes) -> List[dict]:
    """Parse .csv bytes → list of dicts with mapped keys."""
    text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = _csv_module.DictReader(io.StringIO(text))
    result = []
    for row in reader:
        record = {}
        for raw_key, val in row.items():
            db_col = _IMPORT_COLUMN_MAP.get(raw_key.strip(), None)
            if db_col and val and val.strip():
                record[db_col] = val.strip()
        result.append(record)
    return result


@router.post("/import/candidates")
async def import_candidates(
    file: UploadFile = File(...),
    admin: dict = Depends(verify_admin),
):
    """
    Bulk-import candidates from an Excel (.xlsx) or CSV (.csv) file.
    Duplicate phone numbers are skipped (upsert on phone_number).
    Returns per-row import stats.
    """
    filename = file.filename or ""
    file_bytes = await file.read()

    try:
        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            rows = _parse_excel_rows(file_bytes)
        elif filename.endswith(".csv"):
            rows = _parse_csv_rows(file_bytes)
        else:
            # Try CSV as default
            rows = _parse_csv_rows(file_bytes)
    except Exception as parse_err:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {parse_err}")

    if not rows:
        raise HTTPException(status_code=400, detail="File is empty or has no data rows")

    supabase = get_supabase_client()
    imported: List[dict] = []
    skipped: List[dict] = []
    errors: List[dict] = []

    for row_idx, record in enumerate(rows, start=2):
        # Validate required fields
        missing = [f for f in REQUIRED_IMPORT_FIELDS if not record.get(f)]
        if missing:
            errors.append({"row": row_idx, "reason": f"Missing required fields: {missing}", "data": record})
            continue

        # Coerce numeric fields
        for num_field in ("years_of_experience", "expected_salary"):
            if num_field in record:
                try:
                    record[num_field] = float(record[num_field])
                except (ValueError, TypeError):
                    record.pop(num_field, None)

        record.setdefault("company_name", "Qabalan")
        record.setdefault("application_source", "excel_import")

        try:
            result = (
                supabase.table("candidates")
                .upsert(record, on_conflict="phone_number", ignore_duplicates=False)
                .execute()
            )
            if result.data:
                imported.append({"row": row_idx, "id": result.data[0].get("id"), "name": record.get("full_name")})
            else:
                skipped.append({"row": row_idx, "reason": "duplicate phone_number", "name": record.get("full_name")})
        except Exception as insert_err:
            err_msg = str(insert_err)
            if "23505" in err_msg or "duplicate" in err_msg.lower():
                skipped.append({"row": row_idx, "reason": "duplicate phone_number", "name": record.get("full_name")})
            else:
                errors.append({"row": row_idx, "reason": err_msg, "data": record})

    logger.info(
        "Import by %s: %d imported, %d skipped, %d errors (file: %s)",
        admin.get("email"), len(imported), len(skipped), len(errors), filename,
    )

    return {
        "status": "completed",
        "imported": len(imported),
        "skipped": len(skipped),
        "error_count": len(errors),
        "errors": errors,
        "rows": imported,
    }


# ─── Registration Weights CRUD ───────────────────────────────────────────────

@router.get("/registration-weights")
async def list_registration_weights(
    role_target: Optional[str] = None,
    admin: dict = Depends(verify_admin),
):
    """List all registration scoring weights, optionally filtered by role."""
    try:
        supabase = get_supabase_client()
        query = supabase.table("registration_weights").select("*").eq("is_active", True).order("display_order")
        if role_target:
            query = query.eq("role_target", role_target)
        result = query.execute()
        return {"weights": result.data or []}
    except Exception as e:
        logger.error("Error listing registration weights: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class RegistrationWeightUpdate(BaseModel):
    weight: Optional[float] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


@router.patch("/registration-weights/{weight_id}")
async def update_registration_weight(
    weight_id: int,
    body: RegistrationWeightUpdate,
    admin: dict = Depends(verify_admin),
):
    """Update a registration weight value or active status."""
    try:
        supabase = get_supabase_client()
        update_data = {k: v for k, v in body.dict().items() if v is not None}
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Validate weight range
        if "weight" in update_data and not (0 <= update_data["weight"] <= 1):
            raise HTTPException(status_code=400, detail="Weight must be between 0 and 1")
        
        update_data["updated_at"] = datetime.utcnow().isoformat()
        supabase.table("registration_weights").update(update_data).eq("id", weight_id).execute()
        
        logger.info("Registration weight %d updated by %s: %s", weight_id, admin.get("email"), update_data)
        return {"status": "updated", "id": weight_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating registration weight: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── AI Settings CRUD ────────────────────────────────────────────────────────

@router.get("/ai-settings")
async def list_ai_settings(
    admin: dict = Depends(verify_admin),
):
    """List all AI configuration settings."""
    try:
        supabase = get_supabase_client()
        result = (
            supabase.table("ai_settings")
            .select("*")
            .eq("is_editable", True)
            .order("display_order")
            .execute()
        )
        return {"settings": result.data or []}
    except Exception as e:
        logger.error("Error listing AI settings: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class AiSettingUpdate(BaseModel):
    setting_value: str


@router.patch("/ai-settings/{setting_key}")
async def update_ai_setting(
    setting_key: str,
    body: AiSettingUpdate,
    admin: dict = Depends(verify_admin),
):
    """Update an AI setting value."""
    try:
        supabase = get_supabase_client()
        
        # Fetch current setting to validate type
        current = (
            supabase.table("ai_settings")
            .select("data_type, min_value, max_value")
            .eq("setting_key", setting_key)
            .single()
            .execute()
        )
        if not current.data:
            raise HTTPException(status_code=404, detail="Setting not found")
        
        data_type = current.data.get("data_type")
        min_val = current.data.get("min_value")
        max_val = current.data.get("max_value")
        
        # Validate numeric settings
        if data_type == "number":
            try:
                num_val = float(body.setting_value)
                if min_val is not None and num_val < min_val:
                    raise HTTPException(status_code=400, detail=f"Value must be >= {min_val}")
                if max_val is not None and num_val > max_val:
                    raise HTTPException(status_code=400, detail=f"Value must be <= {max_val}")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid number format")
        
        update_data = {
            "setting_value": body.setting_value,
            "updated_at": datetime.utcnow().isoformat(),
        }
        supabase.table("ai_settings").update(update_data).eq("setting_key", setting_key).execute()
        
        logger.info("AI setting %s updated by %s: %s", setting_key, admin.get("email"), body.setting_value)
        return {"status": "updated", "setting_key": setting_key, "new_value": body.setting_value}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating AI setting: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


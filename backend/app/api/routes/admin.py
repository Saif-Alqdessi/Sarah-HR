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

import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel

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
    Tries the materialized view first, falls back to live join query.
    """
    try:
        supabase = get_supabase_client()

        # Try materialized view first (fast)
        try:
            query = supabase.table("mv_admin_dashboard").select("*")

            if search:
                query = query.or_(
                    f"full_name.ilike.%{search}%,"
                    f"target_role.ilike.%{search}%,"
                    f"email.ilike.%{search}%"
                )

            if status:
                query = query.eq("interview_status", status)

            # Sort
            desc = sort_order.lower() == "desc"
            query = query.order(sort_by, desc=desc)

            # Pagination
            query = query.range(offset, offset + limit - 1)

            result = query.execute()

            if result.data is not None:
                return {
                    "candidates": result.data,
                    "total": len(result.data),
                    "offset": offset,
                    "limit": limit,
                    "source": "materialized_view",
                }
        except Exception as mv_err:
            logger.warning("Materialized view query failed, falling back: %s", mv_err)

        # Fallback: live query
        query = supabase.table("candidates").select("*")

        if search:
            query = query.or_(
                f"full_name.ilike.%{search}%,"
                f"target_role.ilike.%{search}%"
            )

        desc = sort_order.lower() == "desc"
        query = query.order(sort_by, desc=desc)
        query = query.range(offset, offset + limit - 1)

        result = query.execute()

        candidates = result.data or []

        # Enrich each candidate with latest interview + score (slower but reliable)
        enriched = []
        for c in candidates:
            cid = c["id"]

            # Latest interview
            int_result = (
                supabase.table("interviews")
                .select("id, status, created_at, completed_at, duration_seconds, "
                        "is_completed, audio_public_url, credibility_score")
                .eq("candidate_id", cid)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            interview = int_result.data[0] if int_result.data else None

            # Latest score (if interview exists)
            score = None
            if interview:
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

            enriched.append({
                **c,
                "interview": interview,
                "score": score,
            })

        return {
            "candidates": enriched,
            "total": len(enriched),
            "offset": offset,
            "limit": limit,
            "source": "live_query",
        }

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
            sj_result = (
                supabase.table("scoring_jobs")
                .select("id, status, created_at, completed_at, error_message")
                .eq("interview_id", interview["id"])
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            scoring_job = sj_result.data[0] if sj_result.data else None

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
    """
    try:
        supabase = get_supabase_client()

        # Total candidates
        candidates_result = supabase.table("candidates").select("id", count="exact").execute()
        total_candidates = candidates_result.count or 0

        # Total interviews
        interviews_result = supabase.table("interviews").select("id", count="exact").execute()
        total_interviews = interviews_result.count or 0

        # Completed interviews
        completed_result = (
            supabase.table("interviews")
            .select("id", count="exact")
            .eq("status", "completed")
            .execute()
        )
        completed_interviews = completed_result.count or 0

        # Average score
        scores_result = supabase.table("scores").select("final_score").execute()
        scores = scores_result.data or []
        avg_score = 0
        if scores:
            avg_score = round(
                sum(s.get("final_score", 0) for s in scores) / len(scores), 1
            )

        # Pending scoring jobs
        pending_result = (
            supabase.table("scoring_jobs")
            .select("id", count="exact")
            .eq("status", "pending")
            .execute()
        )
        pending_jobs = pending_result.count or 0

        return {
            "total_candidates": total_candidates,
            "total_interviews": total_interviews,
            "completed_interviews": completed_interviews,
            "average_score": avg_score,
            "pending_scoring_jobs": pending_jobs,
        }

    except Exception as e:
        logger.error("Error fetching dashboard stats: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

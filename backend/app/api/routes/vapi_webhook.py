"""
Vapi webhook endpoint. Handles end-of-call-report, scores via Gemini, saves to Supabase.
"""

import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from app.integrations.gemini_client import analyze_transcript
from app.db.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/vapi-webhook")
async def vapi_webhook(request: Request):
    """
    Handle Vapi webhook. Specifically processes end-of-call-report:
    - Extracts transcript and call metadata
    - Scores via Gemini
    - Saves to scores table
    - Updates interview status to completed
    """
    try:
        payload = await request.json()
    except Exception as e:
        logger.error("Webhook: failed to parse JSON body: %s", e)
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Log all incoming webhook payloads for debugging
    logger.info("Webhook payload received: %s", payload)

    message = payload.get("message", {})
    msg_type = message.get("type")

    if msg_type != "end-of-call-report":
        logger.info("Webhook: ignoring message type=%s", msg_type)
        return JSONResponse(content={"received": True})

    call = message.get("call", {})
    call_id = call.get("id")
    metadata = call.get("metadata", {})
    candidate_id = metadata.get("candidate_id")
    artifact = message.get("artifact", {})
    transcript = artifact.get("transcript") or ""

    if not transcript:
        logger.warning("Webhook: end-of-call-report has no transcript")
        return JSONResponse(content={"received": True, "warning": "no_transcript"})

    try:
        supabase = get_supabase_client()

        # Try to find interview by vapi_session_id
        int_res = None
        interview_id = None
        
        if call_id:
            int_res = (
                supabase.table("interviews")
                .select("id, candidate_id")
                .eq("vapi_session_id", call_id)
                .execute()
            )
            
            if int_res.data and len(int_res.data) > 0:
                interview = int_res.data[0]
                interview_id = interview["id"]
                if not candidate_id:  # Use candidate_id from database if not in metadata
                    candidate_id = interview["candidate_id"]
        
        # If no interview found by vapi_session_id but we have candidate_id in metadata
        # Try to find the most recent interview for this candidate
        if (not int_res or not int_res.data) and candidate_id:
            logger.info("Webhook: using candidate_id from metadata: %s", candidate_id)
            int_res = (
                supabase.table("interviews")
                .select("id")
                .eq("candidate_id", candidate_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            
            if int_res.data and len(int_res.data) > 0:
                interview_id = int_res.data[0]["id"]
        
        if not interview_id or not candidate_id:
            logger.warning("Webhook: no interview found for vapi_session_id=%s or candidate_id=%s", 
                          call_id, candidate_id)
            return JSONResponse(content={"received": True, "warning": "no_interview"})

        # Get target_role from candidate
        cand_res = (
            supabase.table("candidates")
            .select("target_role")
            .eq("id", candidate_id)
            .single()
            .execute()
        )
        target_role = cand_res.data.get("target_role", "baker") if cand_res.data else "baker"

        # Score via Gemini
        try:
            result = analyze_transcript(transcript, target_role)
        except ValueError as e:
            logger.error("Webhook: Gemini scoring failed: %s", e)
            raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")

        comm = float(result.get("communication_score", 0))
        exp = float(result.get("experience_score", 0))
        sit = float(result.get("situational_score", 0))
        ai_score = min(100, int(comm + exp + sit))
        bottom_line = str(result.get("bottom_line_summary", ""))[:200]
        recommendation = str(result.get("recommendation", "needs_review"))

        # Insert score
        score_data = {
            "interview_id": interview_id,
            "candidate_id": candidate_id,
            "ai_score": ai_score,
            "communication_score": comm,
            "experience_score": exp,
            "situational_score": sit,
            "bottom_line_summary": bottom_line,
            "scoring_model": "gemini-1.5-flash",
        }
        supabase.table("scores").upsert(
            score_data,
            on_conflict="interview_id",
        ).execute()

        # Update interview status
        supabase.table("interviews").update({
            "status": "completed",
            "full_transcript": {"raw": transcript},
        }).eq("id", interview_id).execute()

        logger.info("Webhook: scored and saved for interview_id=%s", interview_id)
        return JSONResponse(content={"received": True, "scored": True})

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Webhook: error processing end-of-call-report: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

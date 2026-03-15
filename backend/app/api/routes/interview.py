"""Interview routes: start, link vapi call, etc."""

import logging
import traceback
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.db.supabase_client import get_supabase_client

router = APIRouter()
logger = logging.getLogger(__name__)


class StartRequest(BaseModel):
    candidate_id: str


class LinkRequest(BaseModel):
    vapi_call_id: str


@router.post("/start")
async def start_interview(req: StartRequest):
    """
    Create an interview record and return its ID.

    Retries up to 3 times on connection timeout (WinError 10060).
    """
    supabase = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "candidate_id": req.candidate_id,
        "status": "in_progress",
        "started_at": now_iso,
        "full_transcript": [],
        "detected_inconsistencies": [],
    }

    max_retries = 3
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            res = supabase.table("interviews").insert(payload).execute()

            if not res.data or len(res.data) == 0:
                logger.error("Interview insert returned no data. Response: %s", res)
                raise HTTPException(status_code=500, detail="Failed to create interview")

            row = res.data[0]
            logger.info(
                "✅ Interview record created: %s (candidate: %s, attempt %d)",
                row["id"], req.candidate_id, attempt,
            )
            return {
                "interview_id": str(row["id"]),
                "started_at": now_iso,
                "status": "in_progress",
            }

        except HTTPException:
            raise  # Don't retry FastAPI exceptions

        except Exception as e:
            last_error = e
            logger.warning(
                "Interview start attempt %d/%d failed: %s",
                attempt, max_retries, e,
            )
            if attempt < max_retries:
                await asyncio.sleep(2.0 * attempt)  # 2s, 4s backoff

    # All retries exhausted
    logger.exception("Interview start failed after %d attempts: %s", max_retries, last_error)
    detail = str(last_error)
    if "row-level security" in detail.lower() or "policy" in detail.lower() or "42501" in detail:
        detail += " Add SUPABASE_SERVICE_ROLE_KEY to backend .env (Dashboard > Settings > API > service_role)."
    raise HTTPException(status_code=500, detail=detail)


@router.patch("/{interview_id}/link")
async def link_vapi_call(interview_id: str, req: LinkRequest):
    """Link Vapi call ID to interview for webhook lookup."""
    try:
        supabase = get_supabase_client()
        supabase.table("interviews").update({
            "vapi_session_id": req.vapi_call_id,
        }).eq("id", interview_id).execute()
        return {"linked": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

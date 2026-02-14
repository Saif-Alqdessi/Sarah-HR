"""Interview routes: start, link vapi call, etc."""

import logging
import traceback

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
    """Create interview record. Returns interview_id for linking to Vapi call."""
    try:
        supabase = get_supabase_client()
        res = (
            supabase.table("interviews")
            .insert({
                "candidate_id": req.candidate_id,
                "status": "in_progress",
            })
            .execute()
        )
        if not res.data or len(res.data) == 0:
            logger.error("Interview insert returned no data. Response: %s", res)
            raise HTTPException(status_code=500, detail="Failed to create interview")
        row = res.data[0]
        return {"interview_id": str(row["id"])}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Interview start failed: %s\n%s", e, traceback.format_exc())
        detail = str(e)
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

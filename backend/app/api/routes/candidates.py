"""
Candidate routes — Qabalan Registration System
Handles candidate creation (registration form) and data retrieval.
"""

import logging
from typing import Optional, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db.supabase_client import get_supabase_client

router = APIRouter()
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Registration Model — matches the frontend form
# ─────────────────────────────────────────────

class CandidateCreate(BaseModel):
    """All fields from the Qabalan registration form."""

    # Section 1: Personal
    full_name: str
    phone_number: str
    date_of_birth: Optional[str] = None
    gender: Optional[str] = "ذكر"
    nationality: Optional[str] = "أردني"
    marital_status: Optional[str] = None
    detailed_residence: Optional[str] = None

    # Section 2: Job
    target_role: str
    years_of_experience: Optional[int] = Field(default=0, ge=0, le=50)
    has_field_experience: Optional[str] = "لا"
    expected_salary: Optional[int] = Field(default=None, ge=200, le=2000)
    preferred_schedule: Optional[str] = None
    can_start_immediately: Optional[str] = None

    # Section 3: Additional
    age_range: Optional[str] = None
    academic_status: Optional[str] = None
    academic_qualification: Optional[str] = None
    proximity_to_branch: Optional[str] = None
    has_relatives_at_company: Optional[str] = None
    previously_at_qabalan: Optional[str] = "لا"
    social_security_issues: Optional[str] = "لا"

    # Section 4: Commitments
    prayer_regularity: Optional[str] = None
    is_smoker: Optional[str] = None
    grooming_objection: Optional[str] = None

    # Meta (set by frontend, not user-visible)
    email: Optional[str] = None
    company_name: Optional[str] = "Qabalan"
    application_source: Optional[str] = "web_form"
    registration_form_data: Optional[Any] = None


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@router.post("/")
async def create_candidate(payload: CandidateCreate):
    """Register a new candidate from the form."""
    try:
        supabase = get_supabase_client()

        insert_data = payload.model_dump(exclude_none=False)
        # Ensure company is always Qabalan
        insert_data["company_name"] = "Qabalan"
        insert_data["application_source"] = "web_form"
        # Store full form as JSON backup
        insert_data["registration_form_data"] = payload.model_dump()

        result = (
            supabase.table("candidates")
            .insert(insert_data)
            .execute()
        )

        if not result.data:
            raise Exception("No data returned from insert")

        candidate = result.data[0]
        logger.info("✅ Candidate registered: %s (%s)", candidate.get("id"), payload.full_name)
        return candidate

    except Exception as e:
        error_msg = str(e)
        if "23505" in error_msg:
            raise HTTPException(status_code=409, detail="رقم الهاتف مسجل مسبقاً")
        logger.error("Error creating candidate: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("/{candidate_id}")
async def get_candidate(candidate_id: str):
    """Fetch candidate by ID."""
    try:
        supabase = get_supabase_client()
        result = supabase.table("candidates").select("*").eq("id", candidate_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching candidate %s: %s", candidate_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{candidate_id}/registration-context")
async def get_registration_context(candidate_id: str):
    """Fetch registration context for interview agent."""
    try:
        supabase = get_supabase_client()

        result = supabase.table("candidates").select("*").eq("id", candidate_id).execute()

        if not result.data:
            logger.warning("No registration context for %s", candidate_id)
            return {}

        logger.info("Registration context loaded for %s", candidate_id)
        return result.data[0]

    except Exception as e:
        logger.error("Error fetching registration context: %s", e)
        return {}

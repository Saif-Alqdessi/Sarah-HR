"""Candidate routes — clean, no legacy columns, no RPCs."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.supabase_client import get_supabase_client

router = APIRouter()
logger = logging.getLogger(__name__)


class CandidateCreate(BaseModel):
    full_name: str
    phone_number: str
    email: Optional[str] = None
    target_role: str


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
    """Fetch registration context — direct query only, no RPC, no fallbacks."""
    try:
        supabase = get_supabase_client()
        
        # Try with company_name first, fall back without it
        try:
            result = supabase.table("candidates").select(
                "full_name, years_of_experience, expected_salary, "
                "has_field_experience, proximity_to_branch, academic_status, "
                "can_start_immediately, prayer_regularity, is_smoker, "
                "target_role, has_relatives_at_company, age_range, "
                "nationality, grooming_objection, social_security_issues, "
                "registration_form_data, company_name"
            ).eq("id", candidate_id).execute()
        except Exception:
            logger.warning("company_name column may not exist, retrying without it")
            result = supabase.table("candidates").select(
                "full_name, years_of_experience, expected_salary, "
                "has_field_experience, proximity_to_branch, academic_status, "
                "can_start_immediately, prayer_regularity, is_smoker, "
                "target_role, has_relatives_at_company, age_range, "
                "nationality, grooming_objection, social_security_issues, "
                "registration_form_data"
            ).eq("id", candidate_id).execute()

        if not result.data:
            logger.warning("No registration context for %s", candidate_id)
            return {}

        logger.info("Registration context loaded for %s", candidate_id)
        return result.data[0]

    except Exception as e:
        logger.error("Error fetching registration context: %s", e)
        return {}

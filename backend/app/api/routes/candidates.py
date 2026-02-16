"""Candidate routes: fetch, create, update candidates."""

import logging
import traceback
import asyncio
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Response
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
async def get_candidate(candidate_id: str, response: Response):
    """
    Fetch candidate by ID with proper error handling and timeout
    """
    try:
        # Set a timeout to prevent hanging
        return await asyncio.wait_for(_fetch_candidate(candidate_id), timeout=5.0)
    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching candidate {candidate_id}")
        response.status_code = 504  # Gateway Timeout
        return {"error": "Request timed out while fetching candidate data"}
    except Exception as e:
        logger.exception(f"Error fetching candidate {candidate_id}: {e}\n{traceback.format_exc()}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Candidate not found")
        raise HTTPException(status_code=500, detail=str(e))


async def _fetch_candidate(candidate_id: str) -> Dict[str, Any]:
    """
    Internal function to fetch candidate with detailed error handling
    """
    try:
        supabase = get_supabase_client()
        
        # Use a simple query first to avoid potential issues
        result = supabase.table("candidates").select("*").eq("id", candidate_id).execute()
        
        if not result.data:
            logger.warning(f"No candidate found with ID {candidate_id}")
            raise HTTPException(status_code=404, detail="Candidate not found")
            
        return result.data[0]
    except Exception as e:
        logger.error(f"Database error fetching candidate {candidate_id}: {e}")
        if "null value in column" in str(e):
            # Handle specific null value error
            logger.error("Null value detected in required column")
            raise HTTPException(
                status_code=422, 
                detail="Database schema error: null value in required column"
            )
        raise


@router.get("/{candidate_id}/registration-context")
async def get_registration_context(candidate_id: str):
    """Fetch registration form context for intelligent agent"""
    try:
        supabase = get_supabase_client()
        
        # Try RPC function first
        try:
            result = supabase.rpc('get_registration_context', {
                'p_candidate_id': candidate_id
            }).execute()
            if result.data:
                logger.info(f"✅ Loaded registration context via RPC for {candidate_id}")
                return result.data
        except Exception as rpc_error:
            logger.warning(f"RPC not available, using fallback: {rpc_error}")
        
        # Fallback: direct query
        result = supabase.table("candidates").select(
            "full_name_ar, years_of_experience, expected_salary, "
            "has_field_experience, proximity_to_branch, academic_status, "
            "can_start_immediately, prayer_regularity, is_smoker, "
            "desired_job_title, has_relatives_at_company, age_range, "
            "nationality, grooming_objection, social_security_issues, "
            "registration_form_data"
        ).eq("id", candidate_id).execute()
        
        if not result.data:
            logger.warning(f"No registration context found for {candidate_id}")
            return {}
        
        logger.info(f"✅ Loaded registration context for {candidate_id}")
        return result.data[0]
        
    except Exception as e:
        logger.exception(f"Error fetching registration context: {e}")
        return {}

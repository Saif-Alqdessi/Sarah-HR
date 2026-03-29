"""
Admin dashboard data synchronization
Posts complete interview data after completion

Called from the WebSocket handler when an interview finishes.
"""

import logging
from datetime import datetime
from typing import Dict
from app.models.candidate import CandidateContract
from app.db.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


async def finalize_interview(
    interview_id: str,
    flow_state: Dict,
    contract: CandidateContract
) -> bool:
    """
    Post all interview data to admin dashboard.

    Steps:
      1. Mark interview as complete
      2. Save final flow state data
      3. Queue scoring job
      4. Refresh dashboard materialized view

    Args:
        interview_id: Interview UUID
        flow_state: Flow controller final state
        contract: Candidate contract

    Returns:
        True if finalization succeeded, False otherwise
    """

    logger.info(f"🏁 Finalizing interview {interview_id}")

    supabase = get_supabase_client()

    try:
        # =====================================================================
        # STEP 1: Mark interview as complete via RPC (if available)
        # =====================================================================
        try:
            supabase.rpc('complete_interview', {
                'p_interview_id': interview_id,
                'p_completion_reason': 'natural'
            }).execute()
            logger.info("✅ Interview marked complete via RPC")
        except Exception as rpc_err:
            logger.warning(f"RPC complete_interview not available ({rpc_err}), using direct update")

        # =====================================================================
        # STEP 2: Update interview record with final data
        # =====================================================================
        interview_update = {
            "is_completed": True,
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "categories_completed": flow_state.get("current_category_index", 0),
            "asked_question_ids": flow_state.get("answered_question_ids", []),
            "updated_at": datetime.utcnow().isoformat()
        }

        supabase.table("interviews").update(
            interview_update
        ).eq("id", interview_id).execute()

        logger.info("✅ Interview record updated with final data")

        # =====================================================================
        # STEP 3: Queue scoring job (background worker will process)
        # =====================================================================
        scoring_job = {
            "interview_id": interview_id,
            "candidate_id": str(contract.candidate_id),
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }

        supabase.table("scoring_jobs").insert(scoring_job).execute()

        logger.info("✅ Scoring job queued (will be processed by background worker)")

        # =====================================================================
        # STEP 4: Refresh admin dashboard materialized view
        # =====================================================================
        try:
            supabase.rpc('refresh_admin_dashboard').execute()
            logger.info("✅ Admin dashboard view refreshed")
        except Exception as refresh_error:
            logger.warning(f"Failed to refresh dashboard view: {refresh_error}")
            # Non-critical, continue

        logger.info(f"🎉 Interview {interview_id} finalized successfully")

        return True

    except Exception as e:
        logger.error(f"❌ Failed to finalize interview: {e}", exc_info=True)
        return False

"""
Fact Contract System
Loads candidate data from Supabase and creates immutable CandidateContract.
Also provides a FactVerifier that catches LLM hallucinations before TTS.

NOTE: CandidateContract is defined in app.models.candidate (Single Source of Truth).
      This module re-exports it for backward compatibility.
"""

import re
import logging
from typing import Optional

from app.models.candidate import CandidateContract  # ← Single Source of Truth

logger = logging.getLogger(__name__)


class FactContractLoader:
    """
    Loads candidate data from Supabase and creates immutable contracts
    """

    def __init__(self, supabase_client):
        self.supabase = supabase_client

    def load_contract(self, candidate_id: str, interview_id: str) -> CandidateContract:
        """
        Fetch candidate data from DB and create immutable contract.

        Args:
            candidate_id: UUID of candidate
            interview_id: UUID of interview session

        Returns:
            CandidateContract: Frozen, immutable contract

        Raises:
            ValueError: If candidate not found or data invalid
        """
        # Query database
        result = self.supabase.table("candidates").select(
            "full_name, target_role, years_of_experience, expected_salary, "
            "has_field_experience, proximity_to_branch, can_start_immediately, "
            "academic_status"
        ).eq("id", candidate_id).single().execute()

        if not result.data:
            raise ValueError(f"Candidate {candidate_id} not found in database")

        # Ensure has_field_experience is an Arabic string, not a boolean
        raw_exp = result.data.get('has_field_experience', 'لا')
        if isinstance(raw_exp, bool):
            has_field_exp = 'نعم' if raw_exp else 'لا'
        else:
            has_field_exp = str(raw_exp) if raw_exp else 'لا'

        # Create immutable contract (models.candidate.CandidateContract)
        contract = CandidateContract(
            candidate_id=candidate_id,
            interview_id=interview_id,
            full_name=result.data['full_name'],
            target_role=result.data['target_role'],
            years_of_experience=result.data.get('years_of_experience', 0),
            expected_salary=result.data.get('expected_salary', 0),
            has_field_experience=has_field_exp,
            proximity_to_branch=result.data.get('proximity_to_branch'),
            can_start_immediately=result.data.get('can_start_immediately'),
            academic_status=result.data.get('academic_status'),
        )

        logger.info(
            "Contract created for %s (role: %s, exp: %s)",
            contract.full_name, contract.target_role, contract.get_experience_arabic(),
        )

        return contract

    def get_fact_summary(self, contract: CandidateContract) -> str:
        """
        Generate human-readable summary of contract facts.
        Used in system prompts.
        """
        field_exp_ar = "عنده خبرة" if contract.has_field_experience_bool() else "بدون خبرة"
        return f"""
# حقائق المتقدم (من قاعدة البيانات - لا يمكن تغييرها)

- الاسم: {contract.full_name}
- الوظيفة المطلوبة: {contract.target_role}
- عدد سنوات الخبرة: {contract.get_experience_arabic()} ({contract.years_of_experience} سنة بالضبط)
- الراتب المتوقع: {contract.expected_salary} دينار
- خبرة في المجال: {field_exp_ar}
- قرب السكن: {contract.proximity_to_branch or "غير محدد"}

⚠️ هذه الأرقام دقيقة من قاعدة البيانات. إذا ذكرتها، استخدم الأرقام الدقيقة.
"""


class FactVerifier:
    """
    Verifies LLM outputs against contract facts.
    Catches hallucinations before they reach TTS.
    """

    def __init__(self, contract: CandidateContract):
        self.contract = contract

    def verify_response(self, llm_response: str) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Check if LLM response contains any hallucinated facts.

        Returns:
            (is_valid, error_message, corrected_response)
        """
        # Extract all numbers from response
        numbers = re.findall(r'\b(\d+)\s*(سنة|سنوات|سنين|year|years)', llm_response)

        for num, unit in numbers:
            num_int = int(num)

            # Check if this number contradicts experience
            if 0 < num_int < 50:  # Likely an experience mention
                if num_int != self.contract.years_of_experience:
                    error = f"Hallucination: LLM stated {num_int} years, DB says {self.contract.years_of_experience}"

                    # Auto-correct
                    corrected = llm_response.replace(
                        f"{num} {unit}",
                        f"{self.contract.years_of_experience} {unit}"
                    )

                    return False, error, corrected

        # Check salary mentions
        salary_pattern = r'(\d+)\s*(دينار|JOD|جنيه)'
        salary_matches = re.findall(salary_pattern, llm_response)

        for amount, currency in salary_matches:
            if int(amount) != self.contract.expected_salary:
                # Might be hallucination, flag it
                if abs(int(amount) - self.contract.expected_salary) > 100:
                    error = f"Potential salary hallucination: stated {amount}, DB says {self.contract.expected_salary}"

                    corrected = llm_response.replace(
                        f"{amount} {currency}",
                        f"{self.contract.expected_salary} {currency}"
                    )

                    return False, error, corrected

        return True, None, None

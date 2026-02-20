"""
Fact Contract System
Ensures immutable candidate facts throughout interview session
"""

from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional
from datetime import datetime
import hashlib
import json


class CandidateContract(BaseModel):
    """
    Immutable contract representing DB facts for a single interview session.
    Once created, these facts CANNOT be modified.
    """
    
    # Identifiers
    candidate_id: str = Field(..., description="Unique candidate identifier")
    interview_id: str = Field(..., description="Unique interview session identifier")
    
    # Core Facts (IMMUTABLE)
    full_name: str = Field(..., description="Candidate's full name")
    target_role: str = Field(..., description="Position applied for")
    years_of_experience: int = Field(..., ge=0, le=50, description="Years of experience (exact)")
    expected_salary: int = Field(..., ge=0, description="Expected salary in JOD")
    has_field_experience: bool = Field(..., description="Experience in bakery/food industry")
    
    # Additional Context
    proximity_to_branch: Optional[str] = Field(None, description="Distance from residence to branch")
    can_start_immediately: Optional[str] = Field(None, description="Availability to start")
    academic_status: Optional[str] = Field(None, description="Current educational status")
    
    # Contract Metadata
    contract_created_at: datetime = Field(default_factory=datetime.utcnow)
    contract_hash: str = Field(default="", description="SHA256 hash for integrity verification")
    
    @validator('contract_hash', always=True)
    def compute_hash(cls, v, values):
        """Compute contract hash for tamper detection"""
        if not v:  # Only compute if not already set
            data = {
                'candidate_id': values.get('candidate_id'),
                'years_of_experience': values.get('years_of_experience'),
                'expected_salary': values.get('expected_salary'),
                'has_field_experience': values.get('has_field_experience')
            }
            hash_str = json.dumps(data, sort_keys=True)
            return hashlib.sha256(hash_str.encode()).hexdigest()[:12]
        return v
    
    class Config:
        frozen = True  # CRITICAL: Makes all fields immutable
        
    def verify_integrity(self) -> bool:
        """Verify contract hasn't been tampered with"""
        original_hash = self.contract_hash
        # Recompute hash
        temp_dict = self.dict()
        temp_dict.pop('contract_hash')
        temp_dict.pop('contract_created_at')
        new_hash = hashlib.sha256(
            json.dumps(temp_dict, sort_keys=True).encode()
        ).hexdigest()[:12]
        return original_hash == new_hash


class FactContractLoader:
    """
    Loads candidate data from Supabase and creates immutable contracts
    """
    
    def __init__(self, supabase_client):
        self.supabase = supabase_client
    
    async def load_contract(self, candidate_id: str, interview_id: str) -> CandidateContract:
        """
        Fetch candidate data from DB and create immutable contract
        
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
        
        # Create immutable contract
        contract = CandidateContract(
            candidate_id=candidate_id,
            interview_id=interview_id,
            full_name=result.data['full_name'],
            target_role=result.data['target_role'],
            years_of_experience=result.data.get('years_of_experience', 0),
            expected_salary=result.data.get('expected_salary', 0),
            has_field_experience=result.data.get('has_field_experience', False),
            proximity_to_branch=result.data.get('proximity_to_branch'),
            can_start_immediately=result.data.get('can_start_immediately'),
            academic_status=result.data.get('academic_status')
        )
        
        print(f"✅ Contract created for {contract.full_name}")
        print(f"   Experience: {contract.years_of_experience} years")
        print(f"   Hash: {contract.contract_hash}")
        
        return contract
    
    def get_fact_summary(self, contract: CandidateContract) -> str:
        """
        Generate human-readable summary of contract facts
        Used in system prompts
        """
        return f"""
# حقائق المتقدم (من قاعدة البيانات - لا يمكن تغييرها)

- الاسم: {contract.full_name}
- الوظيفة المطلوبة: {contract.target_role}
- عدد سنوات الخبرة: {contract.years_of_experience} سنة (بالضبط)
- الراتب المتوقع: {contract.expected_salary} دينار
- خبرة في المجال: {"نعم" if contract.has_field_experience else "لا"}
- قرب السكن: {contract.proximity_to_branch or "غير محدد"}

⚠️ هذه الأرقام دقيقة من قاعدة البيانات. إذا ذكرتها، استخدم الأرقام الدقيقة.
"""


class FactVerifier:
    """
    Verifies LLM outputs against contract facts
    Catches hallucinations before they reach TTS
    """
    
    def __init__(self, contract: CandidateContract):
        self.contract = contract
    
    def verify_response(self, llm_response: str) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Check if LLM response contains any hallucinated facts
        
        Returns:
            (is_valid, error_message, corrected_response)
        """
        import re
        
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

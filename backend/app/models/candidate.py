# =============================================================================
# CANDIDATE MODELS - ARABIC-FIRST SCHEMA
# backend/app/models/candidate.py
# =============================================================================

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from uuid import UUID


class CandidateRegistrationForm(BaseModel):
    """
    Registration form model - Arabic-first schema
    """
    # Personal Information
    full_name: str = Field(..., min_length=3, max_length=255)
    phone_number: str = Field(..., pattern=r'^07[0-9]{8}$')
    email: Optional[str] = None
    detailed_residence: Optional[str] = None

    # Job Application
    target_role: str = Field(..., description="Must be bakery-related role")
    expected_salary: Optional[int] = Field(None, ge=200, le=2000)
    years_of_experience: int = Field(default=0, ge=0, le=50)
    company_name: Optional[str] = Field(default="Qabalan")

    # Demographics (Arabic values)
    date_of_birth: Optional[date] = None
    gender: str = Field(..., pattern=r'^(ذكر|انثى)$')
    age_range: Optional[str] = Field(None, pattern=r'^(18-21|22-25|26 فأكثر)$')
    nationality: str = Field(default='اردني')
    marital_status: Optional[str] = Field(None, pattern=r'^(اعزب|متزوج|مطلق|ارمل)$')

    # Work Preferences
    preferred_schedule: Optional[str] = None
    can_start_immediately: Optional[str] = None
    proximity_to_branch: Optional[str] = None

    # Background (Arabic: نعم/لا - NOT boolean!)
    has_field_experience: str = Field(..., pattern=r'^(نعم|لا)$')
    previously_at_qabalan: str = Field(default='لا', pattern=r'^(نعم|لا)$')
    has_relatives_at_company: Optional[str] = Field(None, pattern=r'^(نعم|لا)$')

    # Education
    academic_status: Optional[str] = None

    # Cultural/Behavioral (Arabic)
    prayer_regularity: Optional[str] = None
    is_smoker: Optional[str] = Field(None, pattern=r'^(نعم|لا)$')
    grooming_objection: Optional[str] = None
    social_security_issues: Optional[str] = Field(default='لا', pattern=r'^(نعم|لا)$')

    @validator('target_role')
    def validate_bakery_role(cls, v):
        """Ensure role is bakery-related"""
        valid_roles = [
            'خباز', 'موظف مبيعات في المعرض', 'سائق توصيل',
            'عامل نظافة', 'تعبئة وتغليف', 'كاشير', 'مدير فرع',
            'مساعد خباز', 'عامل مستودعات'
        ]
        if v not in valid_roles:
            raise ValueError(f'Role must be bakery-related. Got: {v}')
        return v


class CandidateResponse(BaseModel):
    """Response model for candidate data"""
    id: UUID
    full_name: str
    phone_number: str
    email: Optional[str]
    target_role: str
    years_of_experience: int
    expected_salary: Optional[int]
    company_name: Optional[str]
    has_field_experience: str  # Arabic: 'نعم' or 'لا'
    proximity_to_branch: Optional[str]
    can_start_immediately: Optional[str]
    academic_status: Optional[str]
    gender: str
    marital_status: Optional[str]
    interview_count: int
    last_interview_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CandidateContract(BaseModel):
    """
    Immutable contract for interview session
    Updated for Arabic-first schema
    """
    candidate_id: UUID
    interview_id: UUID

    # Core Facts (IMMUTABLE)
    full_name: str
    target_role: str
    years_of_experience: int
    expected_salary: Optional[int]
    has_field_experience: str  # 'نعم' or 'لا'

    # Additional Context
    proximity_to_branch: Optional[str] = None
    can_start_immediately: Optional[str] = None
    academic_status: Optional[str] = None
    company_name: Optional[str] = "Qabalan"

    # Metadata
    contract_created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        frozen = True  # Immutable

    def get_experience_arabic(self) -> str:
        """Get experience in natural Arabic"""
        years = self.years_of_experience
        if years == 0:
            return "بدون خبرة"
        elif years == 1:
            return "سنة واحدة"
        elif years == 2:
            return "سنتين"
        elif 3 <= years <= 10:
            return f"{years} سنوات"
        else:
            return f"{years} سنة"

    def has_field_experience_bool(self) -> bool:
        """Convert Arabic yes/no to boolean"""
        return self.has_field_experience == 'نعم'


# Question Bank Models
class QuestionBankEntry(BaseModel):
    """Model for question bank entry"""
    id: int
    question_id: str
    category_id: int
    category_name_ar: str
    category_name_en: str
    category_stage: str
    question_text_ar: str
    question_text_en: Optional[str]
    weight: float
    is_active: bool
    display_order: Optional[int]

    class Config:
        from_attributes = True


class SelectedQuestion(BaseModel):
    """Model for a selected question during interview"""
    question_id: str
    question_text_ar: str
    category_id: int
    category_name_ar: str
    category_stage: str


# Interview Models
class InterviewUpdate(BaseModel):
    """Model for updating interview progress"""
    status: Optional[str] = None
    current_stage: Optional[str] = None
    categories_completed: Optional[int] = None
    current_category_index: Optional[int] = None
    asked_question_ids: Optional[List[str]] = None
    full_transcript: Optional[List[Dict]] = None
    detected_inconsistencies: Optional[List[Dict]] = None

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date


class CandidateRegistrationForm(BaseModel):
    """
    Pre-interview registration form data
    Matches fields from Excel registration form
    """
    
    # Personal Information
    full_name_ar: Optional[str] = Field(None, description="الاسم الرباعي")
    detailed_residence: Optional[str] = Field(None, description="مكان السكن التفصيلي")
    date_of_birth: Optional[date] = Field(None, description="تاريخ الميلاد")
    gender: Optional[str] = Field(None, description="الجنس")
    marital_status: Optional[str] = Field(None, description="الحالة الاجتماعية")
    
    # Job Preferences
    preferred_schedule: Optional[str] = Field(None, description="نظام الدوام المفضل")
    expected_salary: Optional[str] = Field(None, description="الراتب المتوقع")
    can_start_immediately: Optional[str] = Field(None, description="إمكانية البدء فوراً")
    desired_job_title: Optional[str] = Field(None, description="المسمى الوظيفي المطلوب")
    
    # Background & Experience
    years_of_experience: Optional[str] = Field(None, description="عدد سنوات الخبرة")
    has_field_experience: Optional[str] = Field(None, description="خبرة في نفس المجال")
    academic_status: Optional[str] = Field(None, description="المسار الأكاديمي")
    previously_at_qabalan: Optional[str] = Field(None, description="عمل سابق في قبلان")
    has_relatives_at_company: Optional[str] = Field(None, description="أقارب في الشركة")
    
    # Location & Logistics
    nationality: Optional[str] = Field(None, description="الجنسية")
    age_range: Optional[str] = Field(None, description="الفئة العمرية")
    proximity_to_branch: Optional[str] = Field(None, description="قرب السكن من الفرع")
    
    # Behavioral & Cultural Fit
    prayer_regularity: Optional[str] = Field(None, description="المواظبة على الصلاة")
    is_smoker: Optional[str] = Field(None, description="التدخين")
    grooming_objection: Optional[str] = Field(None, description="مانع من تهذيب الشعر")
    social_security_issues: Optional[str] = Field(None, description="مشاكل الضمان")
    
    # Metadata
    form_submitted_at: Optional[datetime] = None
    registration_form_data: Optional[Dict[str, Any]] = None  # Complete raw form


class CandidateBase(BaseModel):
    full_name: str
    phone_number: str
    email: Optional[str] = None
    target_role: str


class CandidateCreate(BaseModel):
    """
    Complete candidate creation payload including registration form
    """
    # Basic info (existing fields)
    full_name: str
    phone_number: str
    email: Optional[str] = None
    target_role: str
    
    # NEW: Registration form data
    registration_form: Optional[CandidateRegistrationForm] = None
    application_source: str = "web_form"


class CandidateResponse(BaseModel):
    """
    Candidate data returned to frontend
    """
    id: str
    full_name: str
    phone_number: str
    email: Optional[str]
    target_role: str
    
    # Registration context
    registration_form: Optional[CandidateRegistrationForm]
    
    # Interview tracking
    interview_status: Optional[str]
    latest_score: Optional[int]
    
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class Candidate(CandidateBase):
    id: str
    application_source: str

    class Config:
        from_attributes = True

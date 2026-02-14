from pydantic import BaseModel
from typing import Optional


class InterviewCreate(BaseModel):
    candidate_id: str


class Interview(BaseModel):
    id: str
    candidate_id: str
    vapi_session_id: Optional[str] = None
    status: str = "pending"

    class Config:
        from_attributes = True

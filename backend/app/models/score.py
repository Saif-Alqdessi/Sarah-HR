from pydantic import BaseModel
from typing import Optional


class ScoreCreate(BaseModel):
    interview_id: str
    candidate_id: str
    ai_score: int


class Score(BaseModel):
    id: str
    interview_id: str
    candidate_id: str
    ai_score: int
    bottom_line_summary: Optional[str] = None

    class Config:
        from_attributes = True

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.integrations.gemini_client import analyze_transcript

router = APIRouter()


class AnalyzeRequest(BaseModel):
    transcript: str
    target_role: str


@router.post("/analyze")
async def analyze_interview(request: AnalyzeRequest):
    """Analyze interview transcript using Gemini 1.5 Flash. Ready for Vapi webhook integration."""
    try:
        result = analyze_transcript(
            transcript=request.transcript,
            target_role=request.target_role,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")


@router.get("/{interview_id}")
async def get_score(interview_id: str):
    return {"interview_id": interview_id, "score": None}

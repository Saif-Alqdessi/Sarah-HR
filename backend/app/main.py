from dotenv import load_dotenv
load_dotenv()  # Load environment variables before any other imports

import os
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Import traditional REST routes
from app.api.routes import agent, interview, scoring, analytics, transcription, candidates

# Import new WebSocket handler
from app.api.websocket.interview_ws import InterviewWebSocketHandler

# Import Supabase client (used by inline endpoints below)
from app.db.supabase_client import get_supabase_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title="Golden Crust AI Recruiter API",
    description="AI-powered interview orchestration and scoring",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(interview.router, prefix="/api/interview", tags=["interview"])
app.include_router(scoring.router, prefix="/api/scoring", tags=["scoring"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(candidates.router, prefix="/api/candidates", tags=["candidates"])
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
app.include_router(transcription.router, prefix="/api", tags=["transcription"])

# Initialize WebSocket handler
ws_handler = InterviewWebSocketHandler()


@app.get("/")
async def root():
    return {"message": "Golden Crust AI Recruiter API", "status": "running"}


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "architecture": "agentic_langgraph",
        "version": "2.0.0"
    }


@app.get("/api/candidates/{candidate_id}")
async def get_candidate(candidate_id: str):
    """
    Legacy REST endpoint for frontend compatibility
    Fetches candidate data from Supabase
    """
    try:
        supabase = get_supabase_client()
        
        result = supabase.table("candidates").select(
            "id, full_name, phone_number, email, target_role, "
            "years_of_experience, expected_salary, has_field_experience, "
            "proximity_to_branch, can_start_immediately, academic_status, "
            "created_at, updated_at"
        ).eq("id", candidate_id).execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        candidate = result.data[0]
        
        print(f"✅ Fetched candidate: {candidate.get('full_name', 'Unknown')}")
        
        return candidate
        
    except Exception as e:
        print(f"❌ Error fetching candidate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/interview/{candidate_id}")
async def websocket_interview(websocket: WebSocket, candidate_id: str):
    """
    WebSocket endpoint for real-time interview with Sarah AI
    Provides full-duplex audio communication with STT → LLM → TTS pipeline
    
    Args:
        websocket: WebSocket connection
        candidate_id: Candidate ID for loading registration data
    """
    try:
        await ws_handler.handle_interview(websocket, candidate_id)
    except WebSocketDisconnect:
        logging.info(f"WebSocket disconnected for candidate {candidate_id}")
    except Exception as e:
        logging.error(f"Error in interview WebSocket: {str(e)}", exc_info=True)

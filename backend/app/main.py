from dotenv import load_dotenv
load_dotenv()  # Load environment variables before any other imports

import os
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Import traditional REST routes
from app.api.routes import agent, interview, scoring, analytics, transcription, candidates

# Import new WebSocket handler
from app.api.websocket.interview_ws import InterviewWebSocketHandler

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
    return {"status": "healthy"}


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

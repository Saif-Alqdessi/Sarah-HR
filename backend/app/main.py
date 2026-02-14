import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import agent, interview, scoring, analytics, vapi_webhook, transcription

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
app.include_router(agent.router, prefix="/api", tags=["agent"])
app.include_router(vapi_webhook.router, prefix="/api", tags=["webhook"])
app.include_router(transcription.router, prefix="/api", tags=["transcription"])


@app.get("/")
async def root():
    return {"message": "Golden Crust AI Recruiter API", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

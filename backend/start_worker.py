"""
Startup script for the Sarah AI Background Scoring Worker.
Run independently from the main FastAPI server.

Usage:
    cd backend
    python start_worker.py
"""

import asyncio
import logging
import sys
import os

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.workers.scoring_worker import run_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

if __name__ == "__main__":
    print("🚀 Starting Sarah AI Scoring Worker...")
    print("   Press Ctrl+C to stop")
    print()
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        print("\n🛑 Worker stopped")

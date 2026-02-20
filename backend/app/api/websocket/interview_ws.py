"""
WebSocket Orchestrator for Real-Time Voice Interviews
Full control over STT → LLM → TTS pipeline
"""

from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from typing import Dict
import asyncio
import logging
import uuid
from datetime import datetime

from app.core.interview_agent import InterviewAgent
from app.core.fact_contract import FactContractLoader
from app.services.groq_transcriber import GroqTranscriber
from app.services.elevenlabs_tts import ElevenLabsTTS
from app.db.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


class InterviewWebSocketHandler:
    """
    Handles WebSocket connection for a single interview session
    """
    
    def __init__(self):
        self.agent = InterviewAgent()
        self.groq_stt = GroqTranscriber()
        self.tts = ElevenLabsTTS()
        self.supabase = get_supabase_client()
        
        # Session tracking
        self.active_sessions: Dict[str, dict] = {}
    
    async def handle_interview(
        self,
        websocket: WebSocket,
        candidate_id: str
    ):
        """
        Main WebSocket handler for interview session
        
        Message format:
        Client → Server: {"type": "audio", "data": base64_audio}
        Server → Client: {"type": "audio", "data": base64_audio}
                         {"type": "metadata", "stage": "opening", "turn": 1}
        """
        await websocket.accept()
        
        # Generate interview ID
        interview_id = str(uuid.uuid4())
        
        try:
            # STEP 1: Load immutable contract from DB
            logger.info(f"🔄 Loading contract for candidate {candidate_id}")
            
            contract_loader = FactContractLoader(self.supabase)
            contract = await contract_loader.load_contract(candidate_id, interview_id)
            
            logger.info(f"✅ Contract loaded: {contract.full_name}, {contract.years_of_experience} years exp")
            
            # Initialize interview state
            interview_state = {
                "contract": contract,
                "current_stage": "opening",
                "questions_asked": [],
                "conversation_history": [],
                "detected_inconsistencies": [],
                "interview_id": interview_id,
                "started_at": datetime.utcnow(),
                "turn_count": 0
            }
            
            # Store in active sessions
            self.active_sessions[interview_id] = interview_state
            
            # STEP 2: Send opening message
            await self._send_opening_message(websocket, contract, interview_state)
            
            # STEP 3: Main conversation loop
            while True:
                # Receive audio from client
                message = await websocket.receive_json()
                
                if message.get("type") == "audio":
                    audio_data = message.get("data")
                    
                    # STT: Groq Whisper
                    logger.info("🎤 Transcribing audio...")
                    transcript = await self.groq_stt.transcribe(audio_data)
                    logger.info(f"👤 Candidate: {transcript}")
                    
                    # Check if candidate used English
                    from app.core.persona_enforcer import CandidateLanguageMonitor
                    monitor = CandidateLanguageMonitor()
                    used_english, redirect_msg = monitor.check_candidate_input(transcript)
                    
                    if used_english:
                        # Append gentle redirect
                        transcript += f" [SYSTEM_NOTE: Candidate used English - redirect them]"
                    
                    # Process turn through LangGraph
                    logger.info("🧠 Processing through LangGraph...")
                    interview_state = await self.agent.process_turn(
                        contract=contract,
                        user_input=transcript,
                        current_state=interview_state
                    )
                    
                    system_response = interview_state["conversation_history"][-1]["content"]
                    logger.info(f"🤖 Sarah: {system_response}")
                    
                    # TTS: ElevenLabs
                    logger.info("🔊 Generating audio...")
                    audio_response = await self.tts.synthesize(system_response)
                    
                    # Send audio back to client
                    await websocket.send_json({
                        "type": "audio",
                        "data": audio_response,
                        "metadata": {
                            "text": system_response,
                            "stage": interview_state["current_stage"],
                            "turn": interview_state["turn_count"]
                        }
                    })
                    
                    # Update DB with transcript
                    await self._update_interview_record(
                        interview_id=interview_id,
                        candidate_id=candidate_id,
                        transcript=interview_state["conversation_history"],
                        inconsistencies=interview_state["detected_inconsistencies"]
                    )
                    
                elif message.get("type") == "end":
                    # End interview
                    logger.info(f"📝 Interview {interview_id} ended by client")
                    await self._finalize_interview(interview_id, candidate_id)
                    await websocket.send_json({
                        "type": "status",
                        "status": "completed",
                        "message": "Interview completed"
                    })
                    break
                
        except WebSocketDisconnect:
            logger.warning(f"WebSocket disconnected for interview {interview_id}")
            # Clean up
            if interview_id in self.active_sessions:
                del self.active_sessions[interview_id]
                
        except Exception as e:
            logger.error(f"Error in interview WebSocket: {str(e)}", exc_info=True)
            await websocket.send_json({
                "type": "error",
                "message": f"Interview error: {str(e)}"
            })
            
            # Clean up
            if interview_id in self.active_sessions:
                del self.active_sessions[interview_id]
    
    async def _send_opening_message(
        self, 
        websocket: WebSocket,
        contract: CandidateContract,
        interview_state: Dict
    ):
        """Send initial greeting to start the interview"""
        
        # Generate opening message through LangGraph
        updated_state = await self.agent.process_turn(
            contract=contract,
            user_input="",  # Empty for first turn
            current_state=interview_state
        )
        
        # Extract response
        opening_message = updated_state["latest_system_response"]
        
        # TTS
        audio_response = await self.tts.synthesize(opening_message)
        
        # Send to client
        await websocket.send_json({
            "type": "audio",
            "data": audio_response,
            "metadata": {
                "text": opening_message,
                "stage": updated_state["current_stage"],
                "turn": 0,
                "interview_id": updated_state["interview_id"]
            }
        })
        
        # Update session state
        self.active_sessions[updated_state["interview_id"]] = updated_state
    
    async def _update_interview_record(
        self,
        interview_id: str,
        candidate_id: str,
        transcript: List[Dict],
        inconsistencies: List[Dict]
    ):
        """Update interview record in database"""
        try:
            # Format transcript for storage
            formatted_transcript = []
            for turn in transcript:
                formatted_transcript.append({
                    "role": turn["role"],
                    "content": turn["content"],
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            # Update interview record
            self.supabase.table("interviews").update({
                "transcript": formatted_transcript,
                "detected_inconsistencies": inconsistencies,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", interview_id).execute()
            
            logger.info(f"✅ Updated interview record {interview_id}")
            
        except Exception as e:
            logger.error(f"Error updating interview record: {str(e)}", exc_info=True)
    
    async def _finalize_interview(self, interview_id: str, candidate_id: str):
        """Finalize interview and generate summary"""
        try:
            # Get interview state
            interview_state = self.active_sessions.get(interview_id)
            if not interview_state:
                return
            
            # Mark interview as completed
            self.supabase.table("interviews").update({
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
                "duration_seconds": (datetime.utcnow() - interview_state["started_at"]).total_seconds()
            }).eq("id", interview_id).execute()
            
            # Clean up session
            del self.active_sessions[interview_id]
            
            logger.info(f"✅ Interview {interview_id} finalized")
            
        except Exception as e:
            logger.error(f"Error finalizing interview: {str(e)}", exc_info=True)

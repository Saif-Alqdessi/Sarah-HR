"""
WebSocket Orchestrator for Real-Time Voice Interviews
MEMORY-FIRST ARCHITECTURE v2: self.is_processing turn-lock, background DB, aggressive VAD.
"""

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
try:
    from websockets.exceptions import ConnectionClosedError
except ImportError:
    ConnectionClosedError = Exception
from typing import Dict, List, Optional
import asyncio
import logging
import uuid
from datetime import datetime

from app.core.interview_agent import InterviewAgent
from app.core.fact_contract import FactContractLoader
from app.models.candidate import CandidateContract
from app.core.persona_enforcer import CandidateLanguageMonitor
from app.core.fallback_responses import get_fallback_response
from app.core.flow_controller import InterviewFlowController
from app.services.groq_transcriber import GroqTranscriber
from app.services.elevenlabs_tts import ElevenLabsTTS
from app.services.credibility_scorer import CredibilityScorer
from app.services.question_selector import DatabaseQuestionSelector
from app.services.enhanced_filters import is_valid_speech_enhanced
from app.utils.admin_sync import finalize_interview
from app.db.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

_MAX_CONSECUTIVE_ERRORS = 5
_MIN_TRANSCRIPT_CHARS = 5
_MIN_AUDIO_SIZE = 500

import re
from typing import Tuple, Set

def is_valid_speech(transcript: str, min_meaningful_words: int = 3) -> Tuple[bool, str]:
    """Semantic Speech Gate - Filters noise from real human speech"""
    if not transcript or len(transcript.strip()) == 0:
        return False, ""
    
    # Store original for logging
    original = transcript
    
    # Step 1: Strip all punctuation and normalize
    cleaned = re.sub(r'[^\w\s]', '', transcript)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # Step 2: Define Arabic filler words (common STT hallucinations)
    arabic_fillers: Set[str] = {
        'أها', 'اها', 'امم', 'اممم', 'آه', 'اه', 'اوه', 'او',
        'يعني', 'كده', 'بس', 'طيب', 'ايوه', 'اي',
        'لا', 'نعم', 'اه نعم', 'لا لا',
        'ها', 'هم', 'هاه', 'اهم',
        'واو', 'ياي', 'ايه', 'هاي'
    }
    
    # Step 3: Define English filler words
    english_fillers: Set[str] = {
        'um', 'uh', 'ah', 'er', 'hmm', 'hm', 'oh', 'erm',
        'yeah', 'yes', 'no', 'yep', 'nope',
        'okay', 'ok', 'well', 'like', 'so'
    }
    
    all_fillers = {f.lower() for f in arabic_fillers | english_fillers}
    
    words = cleaned.split()
    meaningful_words = [
        word.lower() for word in words
        if word.lower() not in all_fillers and len(word) > 1
    ]
    
    unique_meaningful = set(meaningful_words)
    word_count = len(unique_meaningful)
    is_valid = word_count >= min_meaningful_words
    cleaned_text = ' '.join(meaningful_words) if meaningful_words else ""
    
    if not is_valid:
        logger.info(f"🚫 NOISE FILTERED: '{original}' → {word_count} meaningful words (need {min_meaningful_words})")
    else:
        logger.info(f"✅ VALID SPEECH: '{original}' → {word_count} meaningful words: {cleaned_text}")
    
    return is_valid, cleaned_text


# ═══════════════════════════════════════════════════════════════
# Per-session flow controller registry
# ═══════════════════════════════════════════════════════════════
_flow_controllers: Dict[str, InterviewFlowController] = {}


class InterviewWebSocketHandler:
    """
    MEMORY-FIRST WebSocket handler.
    - self.is_processing = True → DROP all incoming audio
    - All DB writes are fire-and-forget via asyncio.create_task
    - Finalization is non-blocking with 60s timeout
    """

    def __init__(self):
        self.agent = InterviewAgent()
        self.groq_stt = GroqTranscriber()
        self.tts = ElevenLabsTTS()
        self.scorer = CredibilityScorer()
        self.supabase = get_supabase_client()

        # MEMORY-FIRST: this dict IS the source of truth, not Supabase
        self.active_sessions: dict = {}

        # ═══ PER-SESSION TURN-LOCKS ═══
        # Maps interview_id -> bool (True = Sarah is processing/speaking)
        self._session_locks: Dict[str, bool] = {}
        # Maps interview_id -> float (timestamp when Sarah finishes speaking)
        self._cooldown_until: Dict[str, float] = {}

        # TTS cooldown duration in seconds
        self.TTS_COOLDOWN_SECONDS = 1.5

    async def handle_interview(self, websocket: WebSocket, candidate_id: str):
        try:
            await websocket.accept()
        except Exception as e:
            logger.error(f"Failed to accept WebSocket: {e}")
            return

        interview_id = str(uuid.uuid4())
        now_iso = datetime.utcnow().isoformat()

        # DB row insert — BACKGROUND (never block)
        asyncio.create_task(self._bg_insert_row(interview_id, candidate_id, now_iso))

        used_fallbacks: List[str] = []
        consecutive_errors: int = 0
        connection_opened_at = asyncio.get_event_loop().time()

        # Initialize interview_state to prevent UnboundLocalError
        interview_state: Dict = {}

        try:
            # ── Load contract ────────────────────────────────────── #
            logger.info("Loading contract for candidate %s", candidate_id)
            contract_loader = FactContractLoader(self.supabase)
            contract = contract_loader.load_contract(candidate_id, interview_id)
            logger.info(
                "Contract loaded: %s | exp=%d yrs | salary=%d JOD",
                contract.full_name,
                contract.years_of_experience,
                contract.expected_salary,
            )

            # ── Initialize state (MEMORY-FIRST) ─────────────────── #
            interview_state = {
                "contract": contract,
                "current_stage": "opening",
                "questions_asked": [],
                "conversation_history": [],
                "detected_inconsistencies": [],
                "interview_id": interview_id,
                "started_at": datetime.utcnow(),
                "turn_count": 0,
                "credibility_score": 100,
                "topics_covered": [],
                "stage_turn_count": 0,
                "current_category_index": 0,
                "asked_question_ids": [],
                "selected_question_id": "",
                "selected_question_text": "",
                "selected_question_category": "",
                "selected_question_stage": "",
                "categories_completed": 0,
                "total_categories": 8,
                "answer_is_valid": True,
                "latest_user_input": "",
                "latest_system_response": "",
            }
            self.active_sessions[interview_id] = interview_state

            # ── Initialize flow controller for this session ────── #
            question_selector = DatabaseQuestionSelector(self.supabase)
            flow_controller = InterviewFlowController(question_selector)
            _flow_controllers[interview_id] = flow_controller

            # ── Opening greeting ─────────────────────────────────── #
            await self._send_opening_message(
                websocket, contract, interview_state, used_fallbacks
            )

            # ══════════════════════════════════════════════════════ #
            #  MAIN CONVERSATION LOOP                                #
            # ══════════════════════════════════════════════════════ #
            while True:
                if websocket.client_state == WebSocketState.DISCONNECTED:
                    logger.info("🔌 Client disconnected, exiting interview loop")
                    break

                try:
                    message = await asyncio.wait_for(
                        websocket.receive_json(), timeout=300.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("⏰ WebSocket receive timeout, sending ping...")
                    try:
                        await websocket.send_json({"type": "ping"})
                        continue
                    except Exception:
                        logger.error("❌ Client not responding to ping, disconnecting")
                        break
                except WebSocketDisconnect:
                    logger.info("Client disconnected (interview %s)", interview_id)
                    break
                except ConnectionClosedError:
                    logger.info("🔌 Connection closed by client")
                    break

                msg_type = message.get("type")

                # ── AUDIO TURN ───────────────────────────────────── #
                if msg_type == "audio":

                    # ═══ PER-SESSION TURN-LOCK CHECK ═══
                    if self._session_locks.get(interview_id, False):
                        logger.debug("🔒 LOCKED [%s] — dropping audio chunk", interview_id[:8])
                        continue

                    # ═══ TTS COOLDOWN CHECK ═══
                    cooldown_end = self._cooldown_until.get(interview_id, 0)
                    now = asyncio.get_event_loop().time()
                    if now < cooldown_end:
                        remaining = cooldown_end - now
                        logger.debug("❄️ COOLDOWN [%s] — %.1fs remaining, dropping", interview_id[:8], remaining)
                        continue

                    audio_data = message.get("data")

                    # Noise kill: too small
                    if not audio_data or len(audio_data) < _MIN_AUDIO_SIZE:
                        continue

                    # ═══ LOCK THIS SESSION ═══
                    self._session_locks[interview_id] = True
                    try:
                        # 1. STT ─────────────────────────────────── #
                        try:
                            transcript = await self.groq_stt.transcribe(audio_data)
                            logger.info("Candidate said: %s", transcript)
                        except Exception as stt_err:
                            logger.error("STT failed: %s", stt_err)
                            consecutive_errors += 1
                            fb = get_fallback_response("error_recovery", used_fallbacks)
                            used_fallbacks.append(fb)
                            await self._safe_send_audio(websocket, fb, interview_state, used_fallbacks)
                            if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                                break
                            continue

                        # ══════════════════════════════════════════ #
                        #  2. FLOW CONTROLLER VALIDATION PIPELINE    #
                        # ══════════════════════════════════════════ #
                        fc = _flow_controllers.get(interview_id)
                        if fc:
                            flow_result = await fc.process_user_response(
                                transcript=str(transcript).strip(),
                                contract=contract,
                            )
                            action = flow_result["action"]
                            flow_message = flow_result["message"]
                            flow_meta = flow_result.get("metadata", {})

                            logger.info(
                                "📋 FlowController action=%s | gate=%s | q#=%d",
                                action,
                                flow_meta.get("gate", "-"),
                                flow_meta.get("question_number", 0),
                            )

                            if action == "clarify":
                                # ─── Clarification (noise or bad answer) ─── #
                                # Send clarification via TTS, do NOT advance
                                await self._safe_send_audio(
                                    websocket, flow_message, interview_state, used_fallbacks
                                )
                                # Record in conversation history
                                interview_state.setdefault("conversation_history", []).append({
                                    "role": "user", "content": str(transcript).strip(),
                                })
                                interview_state["conversation_history"].append({
                                    "role": "assistant", "content": flow_message,
                                })
                                consecutive_errors = 0

                            elif action == "ask_question":
                                # ─── Valid answer → generate LLM response + ask next Q ─── #
                                try:
                                    interview_state = await self.agent.process_turn(
                                        contract=contract,
                                        user_input=str(transcript).strip(),
                                        current_state=interview_state,
                                    )
                                    # Build combined response: agent's reply + next question
                                    agent_reply = interview_state.get("latest_system_response", "")
                                    next_question = flow_message  # from FlowController

                                    if agent_reply:
                                        system_response = f"{agent_reply}\n\n{next_question}"
                                    else:
                                        system_response = next_question

                                    # Sync flow state into interview_state
                                    fc_state = fc.get_state()
                                    interview_state["current_category_index"] = fc_state["current_category_index"]
                                    interview_state["asked_question_ids"] = fc_state["answered_question_ids"]
                                    interview_state["categories_completed"] = len(fc_state["answered_question_ids"])
                                    interview_state["selected_question_text"] = fc_state.get("current_question", "")
                                    interview_state["selected_question_id"] = fc_state.get("current_question_id", "")

                                    consecutive_errors = 0
                                except Exception as agent_err:
                                    logger.error("Agent failed: %s", agent_err)
                                    consecutive_errors += 1
                                    system_response = flow_message  # Just use the question
                                    interview_state.setdefault("conversation_history", []).append({
                                        "role": "assistant", "content": system_response,
                                    })

                                # TTS the combined response
                                await self._safe_send_audio(
                                    websocket, system_response, interview_state, used_fallbacks
                                )

                                logger.info(
                                    "📊 stage=%s | questions=%d/8 | cat_idx=%d",
                                    interview_state.get("current_stage"),
                                    interview_state.get("categories_completed", 0),
                                    interview_state.get("current_category_index", 0),
                                )

                            elif action == "complete":
                                # ─── Interview complete ─── #
                                interview_state["current_stage"] = "closing"

                                # Send closing TTS
                                await self._safe_send_audio(
                                    websocket, flow_message, interview_state, used_fallbacks
                                )

                                # Send completion signal to frontend
                                try:
                                    await websocket.send_json({
                                        "type": "interview_complete",
                                        "interview_id": interview_id,
                                        "message": "Interview completed successfully",
                                        "total_turns": interview_state.get("turn_count", 0),
                                        "categories_completed": interview_state.get("categories_completed", 0),
                                    })
                                    logger.info("📤 Sent interview_complete signal")
                                except Exception as sig_err:
                                    logger.error("Failed to send completion signal: %s", sig_err)

                                # Background: finalize via admin_sync
                                asyncio.create_task(finalize_interview(
                                    interview_id=interview_id,
                                    flow_state=fc.get_state(),
                                    contract=contract,
                                ))

                                # Graceful close after 2s
                                await asyncio.sleep(2)
                                try:
                                    await websocket.close(code=1000, reason="Interview completed")
                                except Exception:
                                    pass
                                break

                        else:
                            # ─── Fallback: no flow controller (shouldn't happen) ─── #
                            logger.warning("No FlowController for %s, using legacy path", interview_id[:8])
                            clean = str(transcript).strip()
                            is_valid, cleaned_transcript = is_valid_speech(clean, min_meaningful_words=3)
                            if not is_valid:
                                self._session_locks[interview_id] = False
                                continue
                            interview_state = await self.agent.process_turn(
                                contract=contract, user_input=cleaned_transcript,
                                current_state=interview_state,
                            )
                            system_response = interview_state["conversation_history"][-1]["content"]
                            await self._safe_send_audio(
                                websocket, system_response, interview_state, used_fallbacks
                            )

                        # ═══ SET COOLDOWN — Sarah just finished speaking ═══
                        self._cooldown_until[interview_id] = (
                            asyncio.get_event_loop().time() + self.TTS_COOLDOWN_SECONDS
                        )

                        # BACKGROUND DB — fire and forget
                        self.active_sessions[interview_id] = interview_state
                        asyncio.create_task(self._bg_upsert_transcript(
                            interview_id, candidate_id, interview_state,
                        ))

                        # Kill switch
                        if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                            closing = get_fallback_response("closing", used_fallbacks)
                            await self._safe_send_audio(websocket, closing, interview_state, used_fallbacks)
                            break

                    finally:
                        # ═══ UNLOCK SESSION — only after TTS is fully sent ═══
                        self._session_locks[interview_id] = False

                # ── END SIGNAL ───────────────────────────────────── #
                elif msg_type == "end":
                    elapsed = asyncio.get_event_loop().time() - connection_opened_at
                    if elapsed < 5.0:
                        logger.warning("Ignoring premature 'end' (%.1fs)", elapsed)
                        continue
                    logger.info("Interview %s ended by client (%.0fs)", interview_id, elapsed)
                    # BACKGROUND finalization — never block
                    asyncio.create_task(self._bg_finalize(interview_id, candidate_id, interview_state))
                    try:
                        await websocket.send_json({
                            "type": "status",
                            "status": "completed",
                            "message": "Interview completed",
                        })
                    except Exception:
                        pass
                    break

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected (interview %s)", interview_id)

        except Exception as fatal:
            logger.critical("Fatal error in interview %s: %s", interview_id, fatal, exc_info=True)
            try:
                await websocket.send_json({
                    "type": "error",
                    "message": "حدث خطأ غير متوقع. نعتذر منك.",
                })
            except Exception:
                pass

        finally:
            # Clean up per-session locks and flow controller
            self._session_locks.pop(interview_id, None)
            self._cooldown_until.pop(interview_id, None)
            _flow_controllers.pop(interview_id, None)
            # Final cleanup — background finalize if not already done
            if interview_id in self.active_sessions:
                asyncio.create_task(self._bg_finalize(
                    interview_id, candidate_id,
                    self.active_sessions.pop(interview_id, {}),
                ))

    # ================================================================== #
    #  TTS — one attempt, then text fallback immediately                  #
    # ================================================================== #

    async def _safe_send_audio(self, websocket: WebSocket, text: str,
                               interview_state: Dict, used_fallbacks: List[str]):
        try:
            audio_data = await self.tts.synthesize(text)
            await websocket.send_json({
                "type": "audio",
                "data": audio_data,
                "metadata": {
                    "text": text,
                    "stage": interview_state.get("current_stage", "unknown"),
                    "turn": interview_state.get("turn_count", 0),
                    "categories_completed": interview_state.get("categories_completed", 0),
                    "category_index": interview_state.get("current_category_index", 0),
                },
            })
        except Exception as tts_err:
            # ONE failure = immediate text fallback. No retries.
            logger.error("TTS failed: %s — text fallback", tts_err)
            try:
                await websocket.send_json({
                    "type": "text_fallback",
                    "text": text,
                    "metadata": {
                        "stage": interview_state.get("current_stage", "unknown"),
                        "turn": interview_state.get("turn_count", 0),
                    },
                })
            except Exception:
                pass

    async def _send_opening_message(self, websocket: WebSocket,
                                     contract: CandidateContract,
                                     interview_state: Dict,
                                     used_fallbacks: List[str]):
        try:
            updated = await self.agent.process_turn(
                contract=contract, user_input="", current_state=interview_state,
            )
            opening = updated.get("latest_system_response", "")
            interview_state.update(updated)
        except Exception as e:
            logger.error("Opening LLM failed: %s — fallback", e)
            opening = get_fallback_response("opening", used_fallbacks)
            used_fallbacks.append(opening)

        await self._safe_send_audio(websocket, opening, interview_state, used_fallbacks)
        self.active_sessions[interview_state["interview_id"]] = interview_state

    # ================================================================== #
    #  BACKGROUND DB — all fire-and-forget                                #
    # ================================================================== #

    async def _bg_insert_row(self, interview_id: str, candidate_id: str, now_iso: str):
        try:
            self.supabase.table("interviews").insert({
                "id": interview_id,
                "candidate_id": candidate_id,
                "status": "in_progress",
                "started_at": now_iso,
                "full_transcript": [],
                "detected_inconsistencies": [],
            }).execute()
            logger.info("BG: interview row created %s", interview_id)
        except Exception as e:
            logger.warning("BG: insert row failed (non-fatal): %s", e)

    async def _bg_upsert_transcript(self, interview_id: str, candidate_id: str, state: Dict):
        try:
            formatted = [
                {"role": t["role"], "content": t["content"], "timestamp": datetime.utcnow().isoformat()}
                for t in state.get("conversation_history", [])
            ]
            self.supabase.table("interviews").upsert({
                "id": interview_id,
                "candidate_id": candidate_id,
                "status": "in_progress",
                "full_transcript": formatted,
                "detected_inconsistencies": state.get("detected_inconsistencies", []),
                "updated_at": datetime.utcnow().isoformat(),
            }).execute()
            logger.info("BG: upsert OK %s (%d turns)", interview_id, len(formatted))
        except Exception as e:
            logger.warning("BG: upsert failed (non-fatal): %s", e)

    async def _bg_finalize(self, interview_id: str, candidate_id: str,
                            final_state: Optional[Dict] = None):
        """Finalization with 60s hard timeout. Runs in background."""
        try:
            await asyncio.wait_for(
                self._do_finalize(interview_id, candidate_id, final_state),
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            logger.error("Finalization timed out (60s) for %s", interview_id)
        except Exception as e:
            logger.error("BG finalize failed: %s", e)
        finally:
            self.active_sessions.pop(interview_id, None)

    async def _do_finalize(self, interview_id: str, candidate_id: str,
                            final_state: Optional[Dict] = None):
        session = self.active_sessions.get(interview_id) or final_state or {}
        started_at = session.get("started_at", datetime.utcnow())
        duration = (datetime.utcnow() - started_at).total_seconds()
        live_score = session.get("credibility_score", 100)

        contract = session.get("contract")
        history = session.get("conversation_history", [])
        inconsistencies = session.get("detected_inconsistencies", [])

        scoring_result: Dict = {}
        if contract and history:
            try:
                scoring_result = self.scorer.score_credibility(
                    registration_form={
                        "years_of_experience": contract.years_of_experience,
                        "expected_salary": contract.expected_salary,
                        "has_field_experience": contract.has_field_experience,
                        "proximity_to_branch": contract.proximity_to_branch,
                        "target_role": contract.target_role,
                        "full_name": contract.full_name,
                    },
                    transcript=history,
                    detected_inconsistencies=inconsistencies,
                )
                logger.info("Credibility: %s/100", scoring_result.get("credibility_score"))
            except Exception as e:
                logger.error("Scorer failed: %s", e)

        final_score = scoring_result.get("credibility_score", live_score)

        # Write only interview-level fields to `interviews` table.
        # Detailed scoring (credibility_score, recommendation, summary, etc.)
        # belongs in the `scores` table and is written by the scoring_worker.
        self.supabase.table("interviews").upsert({
            "id": interview_id,
            "candidate_id": candidate_id,
            "status": "completed",
            "is_completed": True,
            "completed_at": datetime.utcnow().isoformat(),
            "duration_seconds": int(duration),
            "updated_at": datetime.utcnow().isoformat(),
        }).execute()

        logger.info("Interview %s finalized | live_score=%s | dur=%.0fs", interview_id, final_score, duration)

    async def _bg_enqueue_scoring_job(self, interview_id: str, candidate_id: str):
        """Enqueue a scoring job for the background worker to process."""
        try:
            self.supabase.table("scoring_jobs").insert({
                "interview_id": interview_id,
                "candidate_id": candidate_id,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
            logger.info("BG: scoring job enqueued for %s", interview_id)
        except Exception as e:
            logger.warning("BG: failed to enqueue scoring job (non-fatal): %s", e)

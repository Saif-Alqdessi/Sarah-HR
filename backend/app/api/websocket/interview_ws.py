"""
WebSocket Orchestrator for Real-Time Voice Interviews
MEMORY-FIRST ARCHITECTURE v2: self.is_processing turn-lock, background DB, aggressive VAD.
"""

from fastapi import WebSocket, WebSocketDisconnect
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
from app.services.groq_transcriber import GroqTranscriber
from app.services.elevenlabs_tts import ElevenLabsTTS
from app.services.credibility_scorer import CredibilityScorer
from app.db.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

_MAX_CONSECUTIVE_ERRORS = 5
_MIN_TRANSCRIPT_CHARS = 5
_MIN_AUDIO_SIZE = 500


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
        self.active_sessions: Dict[str, dict] = {}

        # ═══ THE TURN-LOCK ═══
        self.is_processing = False

    async def handle_interview(self, websocket: WebSocket, candidate_id: str):
        await websocket.accept()

        interview_id = str(uuid.uuid4())
        now_iso = datetime.utcnow().isoformat()

        # DB row insert — BACKGROUND (never block)
        asyncio.create_task(self._bg_insert_row(interview_id, candidate_id, now_iso))

        used_fallbacks: List[str] = []
        consecutive_errors: int = 0

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
            interview_state: Dict = {
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
                "total_categories": 6,
                "answer_is_valid": True,
                "latest_user_input": "",
                "latest_system_response": "",
            }
            self.active_sessions[interview_id] = interview_state

            # ── Opening greeting ─────────────────────────────────── #
            await self._send_opening_message(
                websocket, contract, interview_state, used_fallbacks
            )

            connection_opened_at = asyncio.get_event_loop().time()

            # ══════════════════════════════════════════════════════ #
            #  MAIN CONVERSATION LOOP                                #
            # ══════════════════════════════════════════════════════ #
            while True:
                try:
                    message = await asyncio.wait_for(
                        websocket.receive_json(), timeout=90.0
                    )
                except asyncio.TimeoutError:
                    nudge = "لا تزال هنا؟ خذ وقتك."
                    await self._safe_send_audio(websocket, nudge, interview_state, used_fallbacks)
                    continue
                except WebSocketDisconnect:
                    logger.info("Client disconnected (interview %s)", interview_id)
                    break

                msg_type = message.get("type")

                # ── AUDIO TURN ───────────────────────────────────── #
                if msg_type == "audio":

                    # ═══ TURN-LOCK CHECK (FIRST LINE) ═══
                    if self.is_processing:
                        logger.debug("🔒 LOCKED — dropping audio chunk")
                        continue

                    audio_data = message.get("data")

                    # Noise kill: too small
                    if not audio_data or len(audio_data) < _MIN_AUDIO_SIZE:
                        continue

                    # ═══ LOCK ═══
                    self.is_processing = True
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

                        # 2. AGGRESSIVE VAD ──────────────────────── #
                        clean = str(transcript).strip()
                        if len(clean) < _MIN_TRANSCRIPT_CHARS or not any(c.isalpha() for c in clean):
                            logger.info("🔇 VAD reject (%d chars): '%s'", len(clean), clean[:30])
                            continue

                        # Language monitor (non-fatal)
                        try:
                            mon = CandidateLanguageMonitor()
                            eng, _ = mon.check_candidate_input(transcript)
                            if eng:
                                transcript += " [SYSTEM_NOTE: Candidate used English - redirect them]"
                        except Exception:
                            pass

                        # 3. LLM — LangGraph ─────────────────────── #
                        try:
                            logger.info("Processing through LangGraph...")
                            interview_state = await self.agent.process_turn(
                                contract=contract,
                                user_input=transcript,
                                current_state=interview_state,
                            )
                            system_response = interview_state["conversation_history"][-1]["content"]
                            logger.info("Sarah: %s", system_response)
                            logger.info(
                                "📊 stage=%s | categories=%d/6 | cat_idx=%d | history=%d",
                                interview_state.get("current_stage"),
                                interview_state.get("categories_completed", 0),
                                interview_state.get("current_category_index", 0),
                                len(interview_state.get("conversation_history", [])),
                            )
                            consecutive_errors = 0
                        except Exception as agent_err:
                            logger.error("Agent failed: %s", agent_err)
                            consecutive_errors += 1
                            stage = interview_state.get("current_stage", "generic")
                            system_response = get_fallback_response(stage, used_fallbacks)
                            used_fallbacks.append(system_response)
                            interview_state.setdefault("conversation_history", []).append({
                                "role": "assistant",
                                "content": system_response,
                            })

                        # 4. TTS + send ───────────────────────────── #
                        await self._safe_send_audio(
                            websocket, system_response, interview_state, used_fallbacks
                        )

                        # 5. BACKGROUND DB — fire and forget ──────── #
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
                        # ═══ UNLOCK — only after TTS is sent ═══
                        self.is_processing = False

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
            self.is_processing = False
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
        self.supabase.table("interviews").upsert({
            "id": interview_id,
            "candidate_id": candidate_id,
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "duration_seconds": int(duration),
            "credibility_score": int(final_score),
            "recommendation": scoring_result.get("recommendation",
                self.scorer.get_recommendation_from_score(final_score)),
            "summary": scoring_result.get("bottom_line_summary", ""),
            "scoring_details": scoring_result,
            "updated_at": datetime.utcnow().isoformat(),
        }).execute()

        logger.info("Interview %s finalized | score=%s | dur=%.0fs", interview_id, final_score, duration)

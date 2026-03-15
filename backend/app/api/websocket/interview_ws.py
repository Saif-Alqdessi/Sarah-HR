"""
WebSocket Orchestrator for Real-Time Voice Interviews
BULLETPROOF ARCHITECTURE: turn-lock, memory-first, background DB writes.
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

# Max consecutive per-turn errors before we give up and close gracefully
_MAX_CONSECUTIVE_ERRORS = 5

# Minimum transcription length (chars) to be considered real speech
_MIN_TRANSCRIPT_CHARS = 5

# Minimum base64 audio size to even attempt STT
_MIN_AUDIO_SIZE = 500


class InterviewWebSocketHandler:
    """
    Handles WebSocket connection for a single interview session.
    BULLETPROOF — turn-lock mutex, memory-first state, no DB blocking.
    """

    def __init__(self):
        self.agent = InterviewAgent()
        self.groq_stt = GroqTranscriber()
        self.tts = ElevenLabsTTS()
        self.scorer = CredibilityScorer()
        self.supabase = get_supabase_client()

        # session_id -> state dict (MEMORY-FIRST — this IS the source of truth)
        self.active_sessions: Dict[str, dict] = {}

        # session_id -> bool (TURN-LOCK — prevents simultaneous processing)
        self._processing_lock: Dict[str, bool] = {}

        # Track background DB tasks so we can await them on cleanup
        self._bg_tasks: Dict[str, List[asyncio.Task]] = {}

    # ------------------------------------------------------------------ #
    #  Main entry point                                                    #
    # ------------------------------------------------------------------ #

    async def handle_interview(
        self,
        websocket: WebSocket,
        candidate_id: str,
    ):
        await websocket.accept()

        interview_id = str(uuid.uuid4())
        now_iso = datetime.utcnow().isoformat()

        # Pre-insert DB row (fire-and-forget background)
        self._fire_bg_db(interview_id, self._bg_insert_row(interview_id, candidate_id, now_iso))

        # Per-session fallback tracking
        used_fallbacks: List[str] = []
        consecutive_errors: int = 0

        # Initialize turn-lock
        self._processing_lock[interview_id] = False
        self._bg_tasks[interview_id] = []

        try:
            # ── Load immutable contract ──────────────────────────────── #
            logger.info("Loading contract for candidate %s", candidate_id)
            contract_loader = FactContractLoader(self.supabase)
            contract = contract_loader.load_contract(candidate_id, interview_id)
            logger.info(
                "Contract loaded: %s | exp=%d yrs | salary=%d JOD",
                contract.full_name,
                contract.years_of_experience,
                contract.expected_salary,
            )

            # ── Initialize state (MEMORY-FIRST) ─────────────────────── #
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
                # Question-bank fields
                "current_category_index": 0,
                "asked_question_ids": [],
                "selected_question_id": "",
                "selected_question_text": "",
                "selected_question_category": "",
                "selected_question_stage": "",
                "categories_completed": 0,
                "total_categories": 6,
                "answer_is_valid": True,
            }
            self.active_sessions[interview_id] = interview_state

            # ── Opening greeting ─────────────────────────────────────── #
            await self._send_opening_message(
                websocket, contract, interview_state, used_fallbacks
            )

            connection_opened_at = asyncio.get_event_loop().time()

            # ── Main conversation loop ───────────────────────────────── #
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

                # ── Audio turn ───────────────────────────────────────── #
                if msg_type == "audio":
                    audio_data = message.get("data")

                    # ▸ TURN-LOCK: discard audio while processing
                    if self._processing_lock.get(interview_id, False):
                        logger.debug("🔒 Turn-lock active — discarding audio chunk")
                        continue

                    # ▸ Minimum audio size (noise kill)
                    if not audio_data or len(audio_data) < _MIN_AUDIO_SIZE:
                        continue

                    # ═══ ACQUIRE TURN-LOCK ═══
                    self._processing_lock[interview_id] = True
                    try:
                        # 1. STT
                        try:
                            transcript = await self.groq_stt.transcribe(audio_data)
                            logger.info("Candidate said: %s", transcript)
                        except Exception as stt_err:
                            logger.error("STT failed: %s", stt_err)
                            consecutive_errors += 1
                            fallback = get_fallback_response("error_recovery", used_fallbacks)
                            used_fallbacks.append(fallback)
                            await self._safe_send_audio(websocket, fallback, interview_state, used_fallbacks)
                            if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                                break
                            continue

                        # ▸ AGGRESSIVE VAD: kill noise / symbols / too-short
                        clean = str(transcript).strip()
                        if len(clean) < _MIN_TRANSCRIPT_CHARS or not any(c.isalpha() for c in clean):
                            logger.info("🔇 VAD killed transcript (%d chars): '%s'", len(clean), clean[:30])
                            continue  # silent discard — don't trigger LangGraph

                        # Language monitor (non-fatal)
                        try:
                            monitor = CandidateLanguageMonitor()
                            used_english, _ = monitor.check_candidate_input(transcript)
                            if used_english:
                                transcript += " [SYSTEM_NOTE: Candidate used English - redirect them]"
                        except Exception:
                            pass

                        # 2. LLM — LangGraph agent
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

                        # 3. TTS + send
                        await self._safe_send_audio(
                            websocket, system_response, interview_state, used_fallbacks
                        )

                        # 4. MEMORY-FIRST: state is already in self.active_sessions
                        #    DB write happens in background — NEVER blocks the turn
                        self.active_sessions[interview_id] = interview_state
                        self._fire_bg_db(interview_id, self._bg_upsert_transcript(
                            interview_id, candidate_id, interview_state,
                        ))

                        # Kill switch
                        if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                            closing = get_fallback_response("closing", used_fallbacks)
                            await self._safe_send_audio(websocket, closing, interview_state, used_fallbacks)
                            break

                    finally:
                        # ═══ RELEASE TURN-LOCK ═══
                        self._processing_lock[interview_id] = False

                # ── End signal ───────────────────────────────────────── #
                elif msg_type == "end":
                    elapsed = asyncio.get_event_loop().time() - connection_opened_at
                    if elapsed < 5.0:
                        logger.warning(
                            "Ignoring premature 'end' (%.1f s after open)", elapsed,
                        )
                        continue
                    logger.info("Interview %s ended by client (elapsed %.0fs)", interview_id, elapsed)
                    # Non-blocking finalization with 60s timeout
                    self._fire_bg_db(interview_id, self._bg_finalize(
                        interview_id, candidate_id, interview_state,
                    ))
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
            # Wait for any pending background DB tasks (max 10s)
            await self._drain_bg_tasks(interview_id, timeout=10.0)

            # If finalization hasn't run yet, fire it now
            if interview_id in self.active_sessions:
                try:
                    await asyncio.wait_for(
                        self._do_finalize(interview_id, candidate_id, self.active_sessions.get(interview_id)),
                        timeout=60.0,
                    )
                except Exception as fin_err:
                    logger.error("Finalize cleanup failed: %s", fin_err)
                self.active_sessions.pop(interview_id, None)

            # Cleanup locks
            self._processing_lock.pop(interview_id, None)
            self._bg_tasks.pop(interview_id, None)

    # ------------------------------------------------------------------ #
    #  Background DB helpers (MEMORY-FIRST — never block the turn)         #
    # ------------------------------------------------------------------ #

    def _fire_bg_db(self, interview_id: str, coro):
        """Schedule a coroutine as a background task. Never blocks."""
        task = asyncio.create_task(coro)
        self._bg_tasks.setdefault(interview_id, []).append(task)
        task.add_done_callback(lambda t: self._on_bg_done(t, interview_id))

    def _on_bg_done(self, task: asyncio.Task, interview_id: str):
        """Remove completed tasks from the tracking list."""
        try:
            tasks = self._bg_tasks.get(interview_id, [])
            if task in tasks:
                tasks.remove(task)
            if task.exception():
                logger.warning("BG DB task failed for %s: %s", interview_id, task.exception())
        except Exception:
            pass

    async def _drain_bg_tasks(self, interview_id: str, timeout: float = 10.0):
        """Wait for all pending background tasks to finish."""
        tasks = self._bg_tasks.get(interview_id, [])
        if tasks:
            logger.info("Draining %d background tasks for %s...", len(tasks), interview_id)
            done, pending = await asyncio.wait(tasks, timeout=timeout)
            for t in pending:
                t.cancel()

    async def _bg_insert_row(self, interview_id: str, candidate_id: str, now_iso: str):
        """Background: insert initial interview row."""
        try:
            self.supabase.table("interviews").insert({
                "id": interview_id,
                "candidate_id": candidate_id,
                "status": "in_progress",
                "started_at": now_iso,
                "full_transcript": [],
                "detected_inconsistencies": [],
            }).execute()
            logger.info("Interview row created: %s", interview_id)
        except Exception as e:
            logger.warning("BG insert row failed (non-fatal): %s", e)

    async def _bg_upsert_transcript(self, interview_id: str, candidate_id: str, state: Dict):
        """Background: upsert live transcript. Non-fatal."""
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
            logger.info("BG upsert OK: %s (%d turns)", interview_id, len(formatted))
        except Exception as e:
            logger.warning("BG upsert failed (non-fatal): %s", e)

    async def _bg_finalize(self, interview_id: str, candidate_id: str, state: Dict):
        """Background: finalization with 60s timeout."""
        try:
            await asyncio.wait_for(
                self._do_finalize(interview_id, candidate_id, state),
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            logger.error("Finalization timed out (60s) for %s", interview_id)
        except Exception as e:
            logger.error("BG finalize failed: %s", e)

    # ------------------------------------------------------------------ #
    #  Core helpers                                                        #
    # ------------------------------------------------------------------ #

    async def _safe_send_audio(
        self,
        websocket: WebSocket,
        text: str,
        interview_state: Dict,
        used_fallbacks: List[str],
    ):
        """TTS -> send audio. If TTS fails, send text-only."""
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
            logger.error("TTS failed (%s) — sending text fallback", tts_err)
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

    async def _send_opening_message(
        self,
        websocket: WebSocket,
        contract: CandidateContract,
        interview_state: Dict,
        used_fallbacks: List[str],
    ):
        """Generate and send the opening greeting."""
        try:
            updated_state = await self.agent.process_turn(
                contract=contract,
                user_input="",
                current_state=interview_state,
            )
            opening = updated_state.get("latest_system_response", "")
            interview_state.update(updated_state)
        except Exception as e:
            logger.error("Opening LLM call failed: %s — using fallback", e)
            opening = get_fallback_response("opening", used_fallbacks)
            used_fallbacks.append(opening)

        await self._safe_send_audio(websocket, opening, interview_state, used_fallbacks)
        self.active_sessions[interview_state["interview_id"]] = interview_state

    async def _do_finalize(
        self,
        interview_id: str,
        candidate_id: str,
        final_state: Optional[Dict] = None,
    ):
        """Score the full transcript and write final record to Supabase."""
        try:
            session = self.active_sessions.get(interview_id) or final_state or {}
            started_at = session.get("started_at", datetime.utcnow())
            duration = (datetime.utcnow() - started_at).total_seconds()
            live_score: int = session.get("credibility_score", 100)

            contract: Optional[CandidateContract] = session.get("contract")
            conversation_history: List[Dict] = session.get("conversation_history", [])
            detected_inconsistencies: List[Dict] = session.get("detected_inconsistencies", [])

            scoring_result: Dict = {}
            if contract and conversation_history:
                try:
                    logger.info("Running CredibilityScorer on %d turns...", len(conversation_history))
                    form_snapshot = {
                        "years_of_experience": contract.years_of_experience,
                        "expected_salary": contract.expected_salary,
                        "has_field_experience": contract.has_field_experience,
                        "proximity_to_branch": contract.proximity_to_branch,
                        "target_role": contract.target_role,
                        "full_name": contract.full_name,
                    }
                    scoring_result = self.scorer.score_credibility(
                        registration_form=form_snapshot,
                        transcript=conversation_history,
                        detected_inconsistencies=detected_inconsistencies,
                    )
                    logger.info(
                        "Credibility score: %s / 100 (%s)",
                        scoring_result.get("credibility_score"),
                        scoring_result.get("credibility_level"),
                    )
                except Exception as score_err:
                    logger.error("CredibilityScorer failed: %s", score_err)

            final_score = scoring_result.get("credibility_score", live_score)
            final_level = scoring_result.get(
                "credibility_level",
                self.scorer.get_credibility_level_from_score(final_score),
            )
            final_recommendation = scoring_result.get(
                "recommendation",
                self.scorer.get_recommendation_from_score(final_score),
            )
            final_summary = scoring_result.get("bottom_line_summary", "")

            self.supabase.table("interviews").upsert({
                "id": interview_id,
                "candidate_id": candidate_id,
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
                "duration_seconds": int(duration),
                "credibility_score": int(final_score),
                "recommendation": final_recommendation,
                "summary": final_summary,
                "scoring_details": scoring_result,
                "updated_at": datetime.utcnow().isoformat(),
            }).execute()

            logger.info(
                "Interview %s finalized | score=%s | level=%s | duration=%.0fs",
                interview_id, final_score, final_level, duration,
            )

        except Exception as e:
            logger.error("Error finalizing interview: %s", e, exc_info=True)
        finally:
            self.active_sessions.pop(interview_id, None)

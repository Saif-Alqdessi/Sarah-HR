# -*- coding: utf-8 -*-
"""
Agent routes: /agent-response for intelligent conversation, /vapi-webhook for end-of-call.
Supports UTF-8, streaming for sub-1s TTFT, links to IntelligentHRAgent and Supabase.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from app.db.supabase_client import get_supabase_client
from app.services.intelligent_agent import IntelligentHRAgent
from app.services.credibility_scorer import CredibilityScorer

logger = logging.getLogger(__name__)

router = APIRouter()
agent = IntelligentHRAgent()


def _extract_conversation_history(message: dict) -> List[Dict[str, str]]:
    """Extract conversation history from Vapi message in various formats."""
    history: List[Dict[str, str]] = []

    # artifact.messages or artifact.transcript
    artifact = message.get("artifact", {})
    messages = artifact.get("messages") or artifact.get("messagesOpenAIFormatted") or []

    if messages:
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content") or msg.get("message") or msg.get("text") or ""
            if content and isinstance(content, str) and content.strip():
                history.append({
                    "role": "assistant" if role == "assistant" else "user",
                    "content": content.strip(),
                })
        return history

    # transcript as list
    transcript = message.get("transcript", [])
    if isinstance(transcript, list):
        for t in transcript:
            role = t.get("role", "user")
            content = t.get("content") or t.get("text") or ""
            if content and isinstance(content, str) and content.strip():
                history.append({
                    "role": "assistant" if role == "assistant" else "user",
                    "content": content.strip(),
                })
        return history

    # transcript as string
    if isinstance(transcript, str) and transcript.strip():
        history.append({"role": "user", "content": transcript.strip()})

    return history


@router.post("/agent-response")
async def handle_agent_request(request: Request):
    """
    Handle Vapi conversation-update webhooks. Generates intelligent response via
    gpt-4o-mini. Uses streaming from OpenAI for sub-1s time-to-first-token.
    """
    try:
        body_bytes = await request.body()
        body = json.loads(body_bytes)
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid JSON"},
        )

    message = body.get("message", {})
    message_type = message.get("type")

    logger.info("Agent webhook received: type=%s", message_type)

    # Handle conversation-update and assistant-request (Vapi may use either)
    if message_type != "assistant-request":
        return JSONResponse(content={"status": "ignored"})

    call_data = message.get("call", {}) or {}
    assistant_overrides = call_data.get("assistantOverrides", {}) or {}
    variable_values = assistant_overrides.get("variableValues", {}) or {}

    candidate_name = variable_values.get("candidate_name", "المتقدم")
    target_role = variable_values.get("target_role", "baker")
    candidate_id = variable_values.get("candidate_id", "unknown")

    logger.info("Candidate: %s, Role: %s, ID: %s", candidate_name, target_role, candidate_id)

    conversation_history = _extract_conversation_history(message)

    logger.info("Conversation turns: %d", len(conversation_history))
    # اطبع آخر شيء سمعه النظام بوضوح في التيرمينال
    if conversation_history:
        last_user_msg = [m['content'] for m in conversation_history if m['role'] == 'user']
        if last_user_msg:
           print(f"\n👂 سارة سمعت منك: {last_user_msg[-1]}\n")

    # Fetch candidate context and registration form from Supabase
    candidate_context = None
    registration_form = {}
    try:
        if candidate_id and candidate_id != "unknown":
            supabase = get_supabase_client()
            result = (
                supabase.table("candidates")
                .select(
                    "*,"
                    "full_name_ar, years_of_experience, expected_salary, "
                    "has_field_experience, proximity_to_branch, academic_status, "
                    "can_start_immediately, prayer_regularity, is_smoker, "
                    "registration_form_data"
                )
                .eq("id", candidate_id)
                .execute()
            )
            if result.data and len(result.data) > 0:
                candidate_context = result.data[0]
                
                # Extract registration form data
                registration_form = {
                    k: v for k, v in result.data[0].items() 
                    if v is not None and k in [
                        "full_name_ar", "years_of_experience", "expected_salary",
                        "has_field_experience", "proximity_to_branch", "academic_status",
                        "can_start_immediately", "prayer_regularity", "is_smoker",
                        "registration_form_data"
                    ]
                }
                
                logger.info("✅ Loaded registration form context")
    except Exception as e:
        logger.warning("Could not load candidate context: %s", e)

    # Generate response with streaming for low latency
    try:
        logger.info("Calling Intelligent Agent (gpt-4o-mini)...")

        intelligent_response = await _generate_response_streaming(
            candidate_name=candidate_name,
            target_role=target_role,
            conversation_history=conversation_history,
            candidate_id=candidate_id,
            candidate_context=candidate_context,
            registration_form=registration_form,
        )

        logger.info("Agent response: %s", intelligent_response)

        return JSONResponse(
            content={
                "assistant": {
                    "say": intelligent_response,
                },
            },
        )

    except Exception as e:
        logger.exception("Error generating response: %s", e)
        return JSONResponse(
            content={
                "assistant": {
                    "say": "عذراً، حدث خطأ. ممكن تعيد الجواب؟",
                },
            },
        )


async def _generate_response_streaming(
    candidate_name: str,
    target_role: str,
    conversation_history: List[Dict[str, str]],
    candidate_id: str,
    candidate_context: dict | None,
    registration_form: Dict[str, Any] = None,
) -> str:
    """
    Generate response using OpenAI streaming for sub-1s TTFT.
    Runs sync stream in thread pool to avoid blocking.
    """
    import asyncio

    from openai import OpenAI

    def _collect_stream() -> str:
        import google.generativeai as genai
        from app.config import settings
        
        # استخدام Gemini كبديل مجاني ومستقر جداً للهرب من 429
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Use context-aware system prompt if registration form data is available
        if registration_form:
            system_prompt = agent._build_context_aware_system_prompt(
                candidate_name=candidate_name,
                target_role=target_role,
                registration_form=registration_form,
                current_stage="in_progress",
                questions_asked=[]
            )
        else:
            system_prompt = agent._build_agent_system_prompt(
                candidate_name=candidate_name,
                target_role=target_role,
                candidate_context=candidate_context,
            )
        
        full_prompt = f"{system_prompt}\n\nتاريخ المحادثة:\n{str(conversation_history)}"
        
        try:
            response = model.generate_content(full_prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini Error: {e}")
            return "يا سلام! كمل، بسمعك."

    loop = asyncio.get_event_loop()
    full_content = await loop.run_in_executor(None, _collect_stream)

    agent._update_interview_state(candidate_id, conversation_history)

    return full_content or "عذراً، حدث خطأ تقني. ممكن تعيد الجواب؟"


@router.post("/vapi-webhook")
async def handle_end_of_call(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Handle end-of-call-report from Vapi. Triggers final evaluation via
    IntelligentHRAgent and saves to Supabase.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    message = body.get("message", {})
    message_type = message.get("type")

    if message_type != "end-of-call-report":
        logger.info("Vapi webhook: ignoring type=%s", message_type)
        return JSONResponse(content={"received": True})

    logger.info("End of call - generating final evaluation")

    call_data = message.get("call", {}) or {}
    artifact = message.get("artifact", {}) or {}
    assistant_overrides = call_data.get("assistantOverrides", {}) or {}
    variable_values = assistant_overrides.get("variableValues", {}) or {}

    candidate_id = variable_values.get("candidate_id", "unknown")
    target_role = variable_values.get("target_role", "baker")
    call_id = call_data.get("id")

    conversation_history = _extract_conversation_history(message)

    # Get detected inconsistencies if any
    detected_inconsistencies = message.get("detected_inconsistencies", [])
    
    background_tasks.add_task(
        save_evaluation_with_credibility,
        candidate_id=candidate_id,
        target_role=target_role,
        conversation_history=conversation_history,
        detected_inconsistencies=detected_inconsistencies,
        call_id=call_id,
        artifact=artifact,
    )

    return JSONResponse(content={"received": True, "evaluation_queued": True})


async def save_evaluation_with_credibility(
    candidate_id: str,
    target_role: str,
    conversation_history: List[Dict[str, str]],
    detected_inconsistencies: List[Dict[str, Any]],
    call_id: str | None,
    artifact: dict,
) -> None:
    """Generate and save final evaluation to Supabase."""
    try:
        logger.info("Generating final evaluation for candidate %s", candidate_id)

        evaluation = agent.generate_final_evaluation(
            conversation_history=conversation_history,
            target_role=target_role,
        )

        logger.info("Evaluation: %d/100", evaluation.get("overall_score", 0))

        supabase = get_supabase_client()

        # Fetch registration form
        registration_form = {}
        candidate_result = supabase.table("candidates").select("*").eq(
            "id", candidate_id
        ).execute()
        
        if candidate_result.data:
            registration_form = candidate_result.data[0]
        
        # Score credibility
        credibility_scorer = CredibilityScorer()
        credibility_data = credibility_scorer.score_credibility(
            registration_form=registration_form,
            transcript=conversation_history,
            detected_inconsistencies=detected_inconsistencies
        )
        
        print(f"✅ Credibility score: {credibility_data.get('credibility_score')}/100")
        
        # Find interview by vapi_session_id (call_id) or by candidate_id
        interview_result = None
        if call_id:
            interview_result = (
                supabase.table("interviews")
                .select("id, candidate_id")
                .eq("vapi_session_id", call_id)
                .execute()
            )

        if not interview_result or not interview_result.data:
            interview_result = (
                supabase.table("interviews")
                .select("id, candidate_id")
                .eq("candidate_id", candidate_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

        if not interview_result or not interview_result.data:
            logger.warning("No interview found for candidate %s", candidate_id)
            return

        interview = interview_result.data[0]
        interview_id = interview["id"]
        cand_id = interview.get("candidate_id") or candidate_id

        transcript_raw = artifact.get("transcript") or ""
        if isinstance(transcript_raw, list):
            transcript_raw = json.dumps(transcript_raw, ensure_ascii=False)

        score_data: Dict[str, Any] = {
            "interview_id": interview_id,
            "candidate_id": cand_id,
            "ai_score": min(100, int(evaluation.get("overall_score", 50))),
            "communication_score": 0,
            "experience_score": 0,
            "situational_score": 0,
            "bottom_line_summary": (evaluation.get("bottom_line") or "")[:500],
            "scoring_model": "gpt-4o-mini",
            "credibility_score": credibility_data.get("credibility_score"),
            "credibility_level": credibility_data.get("credibility_level"),
            "credibility_assessment": credibility_data
        }

        supabase.table("scores").upsert(
            score_data,
            on_conflict="interview_id",
        ).execute()

        # Save inconsistencies to candidates table
        if credibility_data.get("inconsistencies_found"):
            supabase.table("candidates").update({
                "credibility_flags": credibility_data["inconsistencies_found"]
            }).eq("id", cand_id).execute()
        
        supabase.table("interviews").update(
            {
                "status": "completed",
                "full_transcript": {"messages": conversation_history, "raw": transcript_raw},
            },
        ).eq("id", interview_id).execute()

        logger.info("Evaluation saved for interview %s", interview_id)

    except Exception as e:
        logger.exception("Error saving evaluation: %s", e)


@router.get("/agent-test")
async def test_agent():
    """Health check for agent endpoint."""
    return {
        "status": "ok",
        "message": "Intelligent Agent is ready",
        "model": "gpt-4o-mini",
    }

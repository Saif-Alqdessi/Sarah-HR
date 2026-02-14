"""
Gemini integration for AI scoring.
Uses Gemini 1.5 Flash to analyze interview transcripts. Returns STRICT JSON ONLY.
"""

import json
import re
import logging
from typing import Any

import google.generativeai as genai

from app.config import settings

logger = logging.getLogger(__name__)

SCORING_PROMPT = """You are an expert HR evaluator for a bakery chain. Analyze this interview transcript and provide structured scoring.

TRANSCRIPT:
{transcript}

ROLE: {target_role}

Evaluate on these dimensions:
1. Communication Quality (0-25): Clarity, coherence, language proficiency
2. Relevant Experience (0-25): Past work alignment with role
3. Situational Responses (0-30): Problem-solving, practical thinking

CRITICAL: Return ONLY valid JSON. No markdown, no code blocks, no prose, no explanation. Output must be parseable JSON only.

Required JSON structure (use these exact keys):
{{
  "communication_score": 22,
  "experience_score": 21,
  "situational_score": 26,
  "bottom_line_summary": "Excellent candidate with 5 years of baking experience and strong problem-solving skills.",
  "recommendation": "strong_hire"
}}

Valid recommendation values only: "strong_hire" | "interview" | "reject" | "needs_review"
"""


def _extract_json(text: str) -> dict[str, Any]:
    """Extract JSON from response with robust parsing. Handles markdown and malformed output."""
    text = text.strip()
    # Remove markdown code blocks if present
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if json_match:
        text = json_match.group(1).strip()
    # Try to find JSON object
    obj_match = re.search(r"\{[\s\S]*\}", text)
    if obj_match:
        text = obj_match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("Gemini JSON parse error: %s. Raw text: %s", e, text[:500])
        raise ValueError(f"Gemini returned malformed JSON: {e}") from e


def analyze_transcript(transcript: str, target_role: str) -> dict[str, Any]:
    """
    Analyze interview transcript using Gemini 1.5 Flash.
    Returns flat structure: communication_score, experience_score, situational_score,
    bottom_line_summary, recommendation.
    """
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not configured")

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = SCORING_PROMPT.format(
        transcript=transcript,
        target_role=target_role,
    )

    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.2,
            top_p=0.8,
            top_k=40,
            max_output_tokens=512,
        ),
    )

    if not response.text:
        raise ValueError("Empty response from Gemini")

    result = _extract_json(response.text)

    required = [
        "communication_score",
        "experience_score",
        "situational_score",
        "bottom_line_summary",
        "recommendation",
    ]
    for key in required:
        if key not in result:
            raise ValueError(f"Missing required field in Gemini response: {key}")

    return result

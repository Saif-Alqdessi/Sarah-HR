"""
AI scoring engine - Uses Gemini client for transcript analysis.
Returns the same JSON structure as defined in the architecture for candidate evaluations.
"""

from app.integrations.gemini_client import analyze_transcript


async def score_interview(transcript: str, target_role: str) -> dict:
    """
    Analyze interview transcript using Gemini 1.5 Flash via gemini_client.
    Returns the same JSON structure as defined in the architecture.

    Structure:
    - scores: { communication, experience, situational, cultural_fit, sentiment, total }
    - sentiment_analysis: { overall, confidence }
    - skills: { matched, missing }
    - bottom_line: str
    - red_flags: list[str]
    - recommendation: str (strong_hire | interview | reject | needs_review)
    """
    return analyze_transcript(transcript, target_role)

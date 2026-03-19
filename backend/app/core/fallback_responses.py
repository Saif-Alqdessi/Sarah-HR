"""
Fallback responses for graceful degradation.
Used when LLM or TTS calls fail — ensures Sarah always says something.
All responses are Jordanian Arabic dialect.
"""

import random
from typing import List, Optional


FALLBACK_RESPONSES = {
    "opening": [
        "مرحباً! أنا سارة من شركة قبلان. كيفك؟ جاهز نبدأ؟",
        "أهلاً! شكراً إنك جيت. خلينا نتعرف على بعض شوي.",
        "مرحباً! أنا سارة، مسؤولة التوظيف. ممكن تحكيلي عن نفسك؟",
    ],
    "experience": [
        "حدثني أكثر عن خبرتك بالشغل.",
        "شو نوع الشغل اللي كنت تعمله قبل؟",
        "وين اشتغلت قبل هون؟",
        "كيف كانت تجربتك بالأعمال السابقة؟",
    ],
    "salary": [
        "شو راتبك المتوقع؟",
        "شو تتوقع من ناحية الراتب؟",
        "ما هو الراتب اللي بيناسبك؟",
    ],
    "skills": [
        "شو المهارات اللي بتحس انك قوي فيها؟",
        "إيش الأشياء اللي بتتقنها أكثر؟",
        "كيف بتوصف نفسك من ناحية المهارات؟",
    ],
    "closing": [
        "تمام، شكراً على وقتك! راح نتواصل معك قريب.",
        "ممتاز! شكراً. فريقنا راح يتواصل معك خلال 48 ساعة.",
        "شكراً جزيلاً! كان حلو الحديث معك. بنتواصل قريباً.",
    ],
    "error_recovery": [
        "معلش ما سمعتك منيح، ممكن تعيد؟",
        "آسف، في مشكلة بسيطة. ممكن تكرر آخر جملة؟",
        "عذراً، ما وصلني صوتك. كمل حكيلي.",
        "لحظة... ممكن تعيد اللي قلته آخر مرة؟",
    ],
    "generic": [
        "ممكن توضح أكثر؟",
        "حلو. وبعدين؟",
        "فهمت. كمل حكيلي.",
        "طيب، شو قصدك بالضبط؟",
        "تمام، شو كمان؟",
    ],
}


def get_fallback_response(
    stage: str = "generic",
    used: Optional[List[str]] = None,
) -> str:
    """
    Return a random fallback response for the given interview stage.

    Args:
        stage: Current interview stage key (opening / experience / salary /
               skills / closing / error_recovery / generic).
        used:  List of already-used strings to avoid repetition within a session.

    Returns:
        A Jordanian Arabic fallback string.
    """
    pool = FALLBACK_RESPONSES.get(stage, FALLBACK_RESPONSES["generic"])

    # Filter out already-used responses so we don't repeat ourselves
    if used:
        available = [r for r in pool if r not in used]
        pool = available if available else pool  # fall back to full pool if exhausted

    return random.choice(pool)

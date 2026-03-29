"""
LLM-based semantic validation
Uses Groq to determine if user response is a meaningful answer

Purpose: Gate 2 — catches answers that pass lexical filters but are still
not meaningful (e.g., "يعني أنا بس" = "I mean, I just")
"""

import json
import random
import logging
from typing import Dict
from app.core.llm_manager import MultiProviderLLM

logger = logging.getLogger(__name__)


class SemanticValidator:
    """
    Validates answer quality using Groq LLM

    Purpose: Catch answers that pass lexical filters but are still
    not meaningful (e.g., "يعني أنا بس" = "I mean, I just")
    """

    def __init__(self):
        self.llm = MultiProviderLLM()

    async def validate_answer(
        self,
        question: str,
        answer: str,
        context: Dict = None
    ) -> Dict:
        """
        Validate if answer is meaningful and relevant

        Args:
            question: The question that was asked
            answer: User's response
            context: Optional context (role, experience, etc.)

        Returns:
            {
                "is_valid": bool,
                "confidence": 0.0-1.0,
                "reason": str,
                "suggestion": str  # Jordanian Arabic clarification
            }
        """

        # Build validation prompt
        system_prompt = """You are an expert validator for Arabic HR interviews.

Your task: Determine if the candidate's response is a MEANINGFUL ANSWER or NOT.

NOT MEANINGFUL examples:
- Noise/fillers: "آه آه", "يعني يعني"
- Incomplete: "أنا بس", "يعني أنا"
- Too vague: "نعم", "لا" (for open questions)
- Incoherent: "أنا يعني بس والله"

MEANINGFUL examples:
- "أنا عندي 10 سنوات خبرة بالخبز"
- "بحب أشتغل بفريق وأتعلم مهارات جديدة"
- "نقطة قوتي هي الالتزام والدقة"

Respond in JSON ONLY (no markdown, no explanation):
{
    "is_valid": true/false,
    "confidence": 0.0-1.0,
    "reason": "brief why",
    "suggestion": "Jordanian Arabic clarification if invalid"
}"""

        user_prompt = f"""Question: "{question}"
Candidate's response: "{answer}"

Is this a meaningful answer?"""

        try:
            # Call Groq LLM
            response = await self.llm.generate(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=200
            )

            # Clean response (remove markdown if present)
            response_text = response.strip()
            if response_text.startswith('```'):
                # Remove markdown code blocks
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            # Parse JSON
            result = json.loads(response_text)

            logger.info(
                f"Semantic validation for '{answer[:40]}': "
                f"valid={result.get('is_valid')}, confidence={result.get('confidence')}"
            )

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")

            # Fallback: assume valid to not block interview
            return {
                "is_valid": True,
                "confidence": 0.5,
                "reason": "json_parse_error",
                "suggestion": ""
            }

        except Exception as e:
            logger.error(f"Semantic validation failed: {e}")

            # Fallback: assume valid
            return {
                "is_valid": True,
                "confidence": 0.5,
                "reason": "validation_error",
                "suggestion": ""
            }

    def get_default_clarification(self, question: str) -> str:
        """
        Get default clarification message in Jordanian Arabic
        """
        clarifications = [
            "ما سمعتك منيح، ممكن تعيد الجواب؟",
            "بدي جواب أوضح، ممكن توضح أكتر؟",
            "مش واضح كتير، ممكن تحكيلي أكتر؟",
            "بدي تفاصيل أكتر، ممكن توسع بالجواب؟"
        ]

        return random.choice(clarifications)

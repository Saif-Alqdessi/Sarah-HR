"""
Sequential Interview Flow Controller with Validation Gates
Ensures questions are asked sequentially and answers validated before advancing

Flow:
  1. Ask question
  2. Receive answer
  3. Validate (lexical + semantic)
  4. If valid: advance to next question
  5. If invalid: request clarification (max 3 attempts)
  6. After 8 questions: complete interview
"""

import logging
from typing import Dict, Optional
from app.models.candidate import CandidateContract
from app.services.question_selector import DatabaseQuestionSelector
from app.core.semantic_validator import SemanticValidator
from app.services.enhanced_filters import is_valid_speech_enhanced

logger = logging.getLogger(__name__)


class InterviewFlowController:
    """
    Controls interview flow with multi-gate validation

    Flow:
      1. Ask question
      2. Receive answer
      3. Validate (lexical + semantic)
      4. If valid: advance to next question
      5. If invalid: request clarification (max 3 attempts)
      6. After 8 questions: complete interview
    """

    def __init__(self, question_selector: DatabaseQuestionSelector):
        self.question_selector = question_selector
        self.semantic_validator = SemanticValidator()

        self.state = {
            "current_category_index": 0,
            "current_question": None,
            "current_question_id": None,
            "current_question_category": None,
            "awaiting_answer": False,
            "validation_attempts": 0,
            "max_validation_attempts": 3,
            "answered_question_ids": [],
            "total_questions_target": 8  # Configurable
        }

    async def start_interview(self) -> Dict:
        """
        Start interview by selecting and returning the first question.

        Returns:
            {
                "action": "ask_question",
                "message": str (question text),
                "metadata": dict
            }
        """
        logger.info("🎤 Starting interview flow")
        return await self._ask_next_question()

    async def process_user_response(
        self,
        transcript: str,
        contract: CandidateContract
    ) -> Dict:
        """
        Process user response through the full validation pipeline.

        Pipeline:
          1. Enhanced lexical filter
          2. LLM semantic validator
          3. Advance or clarify based on validation

        Args:
            transcript: User's speech (from Whisper STT)
            contract: Immutable candidate contract

        Returns:
            {
                "action": "ask_question" | "clarify" | "complete",
                "message": str,
                "metadata": dict
            }
        """

        logger.info(f"Processing user response: '{transcript[:60]}'")

        # =====================================================================
        # VALIDATION GATE 1: Enhanced Lexical Filter
        # =====================================================================
        is_valid_lexical, cleaned_text, lexical_metadata = is_valid_speech_enhanced(
            transcript=transcript,
            min_unique_words=3,
            max_repetition_ratio=0.6,
            min_diversity_score=0.3
        )

        if not is_valid_lexical:
            reason = lexical_metadata.get("reason", "unknown")
            logger.info(f"❌ GATE 1 FAILED: {reason}")

            # Don't count as validation attempt (this is noise, not a bad answer)
            return {
                "action": "clarify",
                "message": "ما سمعتك منيح، ممكن تعيد؟",
                "metadata": {
                    "gate": "lexical",
                    "reason": reason,
                    **lexical_metadata
                }
            }

        logger.info("✅ GATE 1 PASSED: Lexical validation successful")

        # =====================================================================
        # VALIDATION GATE 2: LLM Semantic Validator
        # =====================================================================
        if self.state["awaiting_answer"] and self.state["current_question"]:
            validation = await self.semantic_validator.validate_answer(
                question=self.state["current_question"],
                answer=cleaned_text,
                context={
                    "role": contract.target_role,
                    "experience": contract.years_of_experience
                }
            )

            if not validation.get("is_valid", True):
                logger.info(f"❌ GATE 2 FAILED: {validation.get('reason')}")

                self.state["validation_attempts"] += 1

                # Check if max attempts reached
                if self.state["validation_attempts"] >= self.state["max_validation_attempts"]:
                    logger.warning(
                        f"⚠️ Max validation attempts ({self.state['max_validation_attempts']}) "
                        f"reached for question '{self.state['current_question_id']}'. "
                        f"Accepting answer and moving on."
                    )
                    # Reset attempts and fall through to advance
                    self.state["validation_attempts"] = 0
                else:
                    # Request clarification
                    clarification = validation.get("suggestion") or \
                                   self.semantic_validator.get_default_clarification(
                                       self.state["current_question"]
                                   )

                    return {
                        "action": "clarify",
                        "message": clarification,
                        "metadata": {
                            "gate": "semantic",
                            "attempt": self.state["validation_attempts"],
                            "max_attempts": self.state["max_validation_attempts"],
                            **validation
                        }
                    }

            logger.info(
                f"✅ GATE 2 PASSED: Semantic validation successful "
                f"(confidence: {validation.get('confidence', 0):.2f})"
            )

        # =====================================================================
        # ALL GATES PASSED: Advance to Next Question
        # =====================================================================
        logger.info("✅ All validation gates passed, advancing to next question")

        # Record answered question
        if self.state["current_question_id"]:
            self.state["answered_question_ids"].append(self.state["current_question_id"])
        self.state["validation_attempts"] = 0
        self.state["current_category_index"] += 1

        # Check if interview complete
        if len(self.state["answered_question_ids"]) >= self.state["total_questions_target"]:
            logger.info(
                f"🎉 Interview complete! Answered {len(self.state['answered_question_ids'])} questions"
            )

            return {
                "action": "complete",
                "message": "شكراً كتير على وقتك! المقابلة انتهت. راح نتواصل معك قريباً.",
                "metadata": {
                    "total_questions": len(self.state["answered_question_ids"]),
                    "answered_ids": self.state["answered_question_ids"]
                }
            }

        # Ask next question
        return await self._ask_next_question()

    async def _ask_next_question(self) -> Dict:
        """
        Select and return next question from database.

        Returns:
            {
                "action": "ask_question",
                "message": str,
                "metadata": dict
            }
        """

        # Get current category (1-based)
        category_id = self.state["current_category_index"] + 1

        # Wrap around if we exceed 6 categories (questions repeat in cycle)
        if category_id > 6:
            category_id = ((self.state["current_category_index"]) % 6) + 1

        logger.info(f"Selecting question from category {category_id}")

        # Select random question from database
        question = self.question_selector.select_random_question(
            category_id=category_id,
            exclude_ids=self.state["answered_question_ids"]
        )

        if not question:
            logger.warning(f"No question found for category {category_id}, trying others")

            # Try any category
            for cat_id in range(1, 7):
                question = self.question_selector.select_random_question(
                    category_id=cat_id,
                    exclude_ids=self.state["answered_question_ids"]
                )
                if question:
                    break

            if not question:
                logger.error("❌ No questions available at all! Ending interview.")
                return {
                    "action": "complete",
                    "message": "شكراً على وقتك! المقابلة انتهت.",
                    "metadata": {"error": "no_questions_available"}
                }

        # Update state
        self.state["current_question"] = question["question_text_ar"]
        self.state["current_question_id"] = question["question_id"]
        self.state["current_question_category"] = question["category_name_ar"]
        self.state["awaiting_answer"] = True

        logger.info(
            f"📝 Asking question {question['question_id']} "
            f"from category '{question['category_name_ar']}'"
        )

        return {
            "action": "ask_question",
            "message": question["question_text_ar"],
            "metadata": {
                "question_id": question["question_id"],
                "category_id": category_id,
                "category_name": question["category_name_ar"],
                "question_number": len(self.state["answered_question_ids"]) + 1,
                "total_target": self.state["total_questions_target"]
            }
        }

    def get_state(self) -> Dict:
        """Get current flow state (for persistence)"""
        return self.state.copy()

    def set_state(self, state: Dict):
        """Restore flow state (from persistence)"""
        self.state.update(state)

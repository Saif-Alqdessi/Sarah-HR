# 🎯 MASTER IMPLEMENTATION PROMPT
# Sarah AI - Complete Project Fix
# Multi-Stage Validation + Sequential Flow + Admin Integration

**Target AI**: Gemini 2.0 Flash Thinking / Claude Opus 4.6  
**Complexity**: Very High  
**Estimated Time**: 8-10 hours  
**Impact**: Complete system overhaul

---

## 🎯 MISSION OVERVIEW

You are implementing a **complete overhaul** of the Sarah AI voice interviewer system to fix critical semantic hallucination issues and implement proper interview flow control.

### Current Problems
1. ❌ Whisper hallucinates noise as text ("آه آه آه")
2. ❌ Simple word count filter bypassed by hallucinations
3. ❌ No LLM validation of answer quality
4. ❌ Interview advances before validating answers
5. ❌ Admin dashboard not receiving complete data

### Solution Architecture
```
Multi-Stage Validation Pipeline:
1. Enhanced Lexical Filter (pattern detection)
2. LLM Semantic Validator (Groq-based answer quality check)
3. Sequential Flow Controller (validates before advancing)
4. Admin Dashboard Integration (post-interview data sync)
```

---

## 📁 PROJECT STRUCTURE

```
backend/
├── app/
│   ├── core/
│   │   ├── interview_agent.py          (MODIFY - LangGraph)
│   │   ├── semantic_validator.py       (CREATE NEW)
│   │   └── flow_controller.py          (CREATE NEW)
│   ├── api/
│   │   └── websocket/
│   │       └── interview_ws.py         (MODIFY - WebSocket)
│   ├── services/
│   │   ├── question_selector.py        (NO CHANGE)
│   │   └── enhanced_filters.py         (CREATE NEW)
│   └── utils/
│       └── admin_sync.py               (CREATE NEW)
```

---

## 🔧 IMPLEMENTATION PLAN

### TASK 1: Create Enhanced Lexical Filter

**File**: `backend/app/services/enhanced_filters.py` (NEW FILE)

```python
"""
Enhanced lexical filtering with pattern detection
Catches noise that simple word counts miss
"""

import re
from typing import Tuple, List, Dict, Set
from collections import Counter
import logging

logger = logging.getLogger(__name__)


def is_valid_speech_enhanced(
    transcript: str,
    min_unique_words: int = 3,
    max_repetition_ratio: float = 0.6,
    min_diversity_score: float = 0.3
) -> Tuple[bool, str, Dict]:
    """
    Multi-layer lexical validation with pattern detection
    
    Args:
        transcript: Raw STT output
        min_unique_words: Minimum unique meaningful words required
        max_repetition_ratio: Max allowed repetition (0.6 = 60%)
        min_diversity_score: Minimum lexical diversity (unique/total)
    
    Returns:
        (is_valid, cleaned_text, metadata)
        
    Examples:
        "آه آه آه آه" → (False, "", {"reason": "repetitive_pattern"})
        "يعني يعني بس أنا" → (False, "أنا", {"reason": "low_diversity"})
        "أنا عندي خبرة كبيرة" → (True, "أنا عندي خبرة كبيرة", {"reason": "valid"})
    """
    
    if not transcript or len(transcript.strip()) == 0:
        return False, "", {"reason": "empty"}
    
    original = transcript
    
    # =========================================================================
    # LAYER 1: Basic Cleaning
    # =========================================================================
    # Strip punctuation
    cleaned = re.sub(r'[^\w\s]', '', transcript)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    if not cleaned:
        return False, "", {"reason": "empty_after_cleaning"}
    
    # =========================================================================
    # LAYER 2: Filler Word Removal
    # =========================================================================
    arabic_fillers: Set[str] = {
        # Single syllable noise
        'أها', 'اها', 'امم', 'اممم', 'آه', 'اه', 'او', 'اوه',
        
        # Discourse markers (acceptable in context, but suspicious alone)
        'يعني', 'كده', 'بس', 'طيب', 'ايوه',
        
        # Simple yes/no (need more context)
        'نعم', 'لا', 'اي', 'لأ',
        
        # Hesitation markers
        'ها', 'هم', 'هاه', 'اهم', 'واو', 'ياي', 'ايه'
    }
    
    english_fillers: Set[str] = {
        'um', 'uh', 'ah', 'er', 'hmm', 'hm', 'oh', 'erm',
        'yeah', 'yes', 'no', 'yep', 'nope', 'okay', 'ok', 'well'
    }
    
    all_fillers = {f.lower() for f in arabic_fillers | english_fillers}
    
    # Split into words
    words = cleaned.split()
    
    # Filter out fillers and single characters
    meaningful_words = [
        word for word in words
        if word.lower() not in all_fillers and len(word) > 1
    ]
    
    # =========================================================================
    # LAYER 3: Repetitive Pattern Detection
    # =========================================================================
    if words:
        word_counts = Counter(words)
        most_common_word, max_count = word_counts.most_common(1)[0]
        repetition_ratio = max_count / len(words)
        
        if repetition_ratio > max_repetition_ratio:
            logger.info(
                f"🔁 REPETITIVE PATTERN: '{most_common_word}' appears "
                f"{repetition_ratio:.1%} of the time in '{original}'"
            )
            return False, "", {
                "reason": "repetitive_pattern",
                "word": most_common_word,
                "ratio": repetition_ratio
            }
    
    # =========================================================================
    # LAYER 4: Single Syllable Dominance Detection
    # =========================================================================
    if words:
        single_syllable_count = sum(1 for word in words if len(word) <= 2)
        single_syllable_ratio = single_syllable_count / len(words)
        
        if single_syllable_ratio > 0.7:  # >70% single syllable = noise
            logger.info(
                f"🔤 SINGLE SYLLABLE DOMINANCE: {single_syllable_ratio:.1%} "
                f"in '{original}'"
            )
            return False, "", {
                "reason": "single_syllable_dominant",
                "ratio": single_syllable_ratio
            }
    
    # =========================================================================
    # LAYER 5: Unique Word Count
    # =========================================================================
    unique_meaningful = set(meaningful_words)
    
    if len(unique_meaningful) < min_unique_words:
        logger.info(
            f"📊 INSUFFICIENT UNIQUE WORDS: {len(unique_meaningful)} "
            f"(need {min_unique_words}) in '{original}'"
        )
        return False, ' '.join(meaningful_words), {
            "reason": "insufficient_unique_words",
            "unique_count": len(unique_meaningful),
            "required": min_unique_words
        }
    
    # =========================================================================
    # LAYER 6: Lexical Diversity Score
    # =========================================================================
    diversity_score = len(unique_meaningful) / len(meaningful_words) if meaningful_words else 0
    
    if diversity_score < min_diversity_score:
        logger.info(
            f"📈 LOW DIVERSITY: {diversity_score:.2f} "
            f"(need {min_diversity_score}) in '{original}'"
        )
        return False, ' '.join(meaningful_words), {
            "reason": "low_diversity",
            "diversity": diversity_score,
            "required": min_diversity_score
        }
    
    # =========================================================================
    # ALL LAYERS PASSED
    # =========================================================================
    cleaned_text = ' '.join(meaningful_words)
    
    logger.info(
        f"✅ VALID SPEECH: '{original}' → '{cleaned_text}' "
        f"({len(unique_meaningful)} unique words, {diversity_score:.2f} diversity)"
    )
    
    return True, cleaned_text, {
        "reason": "valid",
        "unique_words": len(unique_meaningful),
        "diversity": diversity_score,
        "original": original,
        "cleaned": cleaned_text
    }


def detect_consecutive_repetition(words: List[str], max_consecutive: int = 3) -> bool:
    """
    Detect consecutive repetition of same word
    
    Example: ["آه", "آه", "آه"] → True (noise)
    Example: ["أنا", "عندي", "خبرة"] → False (valid)
    """
    if len(words) < 2:
        return False
    
    consecutive_count = 1
    
    for i in range(1, len(words)):
        if words[i] == words[i-1]:
            consecutive_count += 1
            if consecutive_count >= max_consecutive:
                return True
        else:
            consecutive_count = 1
    
    return False
```

---

### TASK 2: Create LLM Semantic Validator

**File**: `backend/app/core/semantic_validator.py` (NEW FILE)

```python
"""
LLM-based semantic validation
Uses Groq to determine if user response is a meaningful answer
"""

import json
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
                f"Semantic validation for '{answer}': "
                f"valid={result['is_valid']}, confidence={result['confidence']}"
            )
            
            return result
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Raw response: {response}")
            
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
        
        import random
        return random.choice(clarifications)
```

---

### TASK 3: Create Sequential Flow Controller

**File**: `backend/app/core/flow_controller.py` (NEW FILE)

```python
"""
Sequential Interview Flow Controller with Validation Gates
Ensures questions are asked sequentially and answers validated before advancing
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
        Start interview by asking first question
        
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
        Process user response through validation pipeline
        
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
        
        logger.info(f"Processing user response: '{transcript}'")
        
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
        
        logger.info(f"✅ GATE 1 PASSED: Lexical validation successful")
        
        # =====================================================================
        # VALIDATION GATE 2: LLM Semantic Validator
        # =====================================================================
        if self.state["awaiting_answer"]:
            validation = await self.semantic_validator.validate_answer(
                question=self.state["current_question"],
                answer=cleaned_text,
                context={
                    "role": contract.target_role,
                    "experience": contract.years_of_experience
                }
            )
            
            if not validation["is_valid"]:
                logger.info(f"❌ GATE 2 FAILED: {validation['reason']}")
                
                self.state["validation_attempts"] += 1
                
                # Check if max attempts reached
                if self.state["validation_attempts"] >= self.state["max_validation_attempts"]:
                    logger.warning(
                        f"⚠️ Max validation attempts ({self.state['max_validation_attempts']}) "
                        f"reached for question '{self.state['current_question_id']}'. "
                        f"Accepting answer and moving on."
                    )
                    
                    # Reset attempts and advance
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
        Select and ask next question from database
        
        Returns:
            {
                "action": "ask_question",
                "message": str,
                "metadata": dict
            }
        """
        
        # Get current category (1-6)
        category_id = self.state["current_category_index"] + 1
        
        # Ensure we don't exceed 6 categories
        if category_id > 6:
            category_id = ((self.state["current_category_index"]) % 6) + 1
        
        logger.info(f"Selecting question from category {category_id}")
        
        # Select random question from database
        question = self.question_selector.select_random_question(
            category_id=category_id,
            exclude_ids=self.state["answered_question_ids"]
        )
        
        if not question:
            logger.error(f"❌ No question found for category {category_id}")
            
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
                    "message": "شكراً على وقتك!",
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
```

---

### TASK 4: Update WebSocket Handler

**File**: `backend/app/api/websocket/interview_ws.py` (MODIFY)

**Find** the transcript processing section and REPLACE with:

```python
# Add imports at top
from app.core.flow_controller import InterviewFlowController
from app.services.question_selector import DatabaseQuestionSelector

# Initialize flow controller (in websocket_endpoint function)
question_selector = DatabaseQuestionSelector(supabase)
flow_controller = InterviewFlowController(question_selector)

# Start interview
start_result = await flow_controller.start_interview()

# Send first question
await websocket.send_json({
    "type": "sarah_response",
    "message": start_result["message"],
    "metadata": start_result["metadata"]
})

# Main interview loop
while True:
    try:
        # Receive message
        data = await websocket.receive_json()
        
        if data.get("type") == "transcript":
            transcript = data.get("transcript", "")
            
            logger.info(f"📝 Received transcript: {transcript}")
            
            # =========================================================
            # PROCESS THROUGH VALIDATION PIPELINE
            # =========================================================
            result = await flow_controller.process_user_response(
                transcript=transcript,
                contract=contract
            )
            
            action = result["action"]
            message = result["message"]
            metadata = result.get("metadata", {})
            
            logger.info(f"Action: {action}, Message: {message[:50]}...")
            
            # =========================================================
            # HANDLE ACTIONS
            # =========================================================
            if action == "clarify":
                # Request clarification (answer was invalid)
                await websocket.send_json({
                    "type": "clarification",
                    "message": message,
                    "metadata": metadata
                })
            
            elif action == "ask_question":
                # Ask next question (answer was valid)
                await websocket.send_json({
                    "type": "sarah_response",
                    "message": message,
                    "metadata": metadata
                })
            
            elif action == "complete":
                # Interview complete
                await websocket.send_json({
                    "type": "interview_complete",
                    "message": message,
                    "metadata": metadata
                })
                
                # ================================================
                # FINALIZE INTERVIEW (TASK 5)
                # ================================================
                await finalize_interview(
                    interview_id=interview_id,
                    flow_state=flow_controller.get_state(),
                    contract=contract
                )
                
                break  # Exit loop
        
        # ... handle other message types (audio, etc.)
    
    except WebSocketDisconnect:
        logger.info("Client disconnected")
        break
    
    except Exception as e:
        logger.error(f"Error: {e}")
        break
```

---

### TASK 5: Admin Dashboard Integration

**File**: `backend/app/utils/admin_sync.py` (NEW FILE)

```python
"""
Admin dashboard data synchronization
Posts complete interview data after completion
"""

import logging
from datetime import datetime
from typing import Dict
from app.models.candidate import CandidateContract
from app.db.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


async def finalize_interview(
    interview_id: str,
    flow_state: Dict,
    contract: CandidateContract
):
    """
    Post all interview data to admin dashboard
    
    Steps:
    1. Mark interview as complete
    2. Save final transcript
    3. Queue scoring job
    4. Refresh dashboard view
    
    Args:
        interview_id: Interview UUID
        flow_state: Flow controller final state
        contract: Candidate contract
    """
    
    logger.info(f"🏁 Finalizing interview {interview_id}")
    
    supabase = get_supabase_client()
    
    try:
        # =====================================================================
        # STEP 1: Mark interview as complete
        # =====================================================================
        result = supabase.rpc('complete_interview', {
            'p_interview_id': interview_id,
            'p_completion_reason': 'natural'
        }).execute()
        
        logger.info(f"✅ Interview marked complete via RPC")
        
        # =====================================================================
        # STEP 2: Update interview record with final data
        # =====================================================================
        interview_update = {
            "is_completed": True,
            "completed_at": datetime.utcnow().isoformat(),
            "categories_completed": flow_state.get("current_category_index", 0),
            "final_turn_count": len(flow_state.get("answered_question_ids", [])),
            "asked_question_ids": flow_state.get("answered_question_ids", []),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        supabase.table("interviews").update(interview_update).eq("id", interview_id).execute()
        
        logger.info(f"✅ Interview record updated with final data")
        
        # =====================================================================
        # STEP 3: Queue scoring job (background worker will process)
        # =====================================================================
        scoring_job = {
            "interview_id": interview_id,
            "candidate_id": str(contract.candidate_id),
            "status": "pending",
            "priority": 1,  # High priority
            "created_at": datetime.utcnow().isoformat()
        }
        
        supabase.table("scoring_jobs").insert(scoring_job).execute()
        
        logger.info(f"✅ Scoring job queued (will be processed by background worker)")
        
        # =====================================================================
        # STEP 4: Refresh admin dashboard materialized view
        # =====================================================================
        try:
            supabase.rpc('refresh_admin_dashboard').execute()
            logger.info(f"✅ Admin dashboard view refreshed")
        except Exception as refresh_error:
            logger.warning(f"Failed to refresh dashboard view: {refresh_error}")
            # Non-critical, continue
        
        logger.info(f"🎉 Interview {interview_id} finalized successfully")
        
        return True
    
    except Exception as e:
        logger.error(f"❌ Failed to finalize interview: {e}", exc_info=True)
        return False
```

---

### TASK 6: Update Interview Agent (LangGraph Integration)

**File**: `backend/app/core/interview_agent.py` (MODIFY)

**This file should now be SIMPLIFIED** since flow control is handled by InterviewFlowController.

The LangGraph agent should focus on:
1. Generating Sarah's conversational responses
2. Enforcing persona (Jordanian dialect)
3. NOT managing question selection (that's flow controller's job)

**Key Change**: Remove question selection logic from LangGraph, defer to FlowController.

---

## 🧪 TESTING INSTRUCTIONS

### Test 1: Noise Filtering

```python
# Test cases
test_cases = [
    {
        "input": "آه آه آه آه آه",
        "expected_gate1": False,
        "expected_reason": "repetitive_pattern"
    },
    {
        "input": "يعني يعني يعني بس",
        "expected_gate1": False,
        "expected_reason": "low_diversity"
    },
    {
        "input": "أنا عندي خبرة كبيرة بالخبز",
        "expected_gate1": True,
        "expected_gate2": True
    },
    {
        "input": "يعني أنا بس",
        "expected_gate1": True,  # Passes lexical
        "expected_gate2": False  # Fails semantic
    }
]

# Run tests
for test in test_cases:
    is_valid, cleaned, metadata = is_valid_speech_enhanced(test["input"])
    assert is_valid == test["expected_gate1"], f"Failed for: {test['input']}"
```

### Test 2: Sequential Flow

```bash
# Manual interview test
1. Start interview
2. Make noise ("آه آه آה") → Should clarify
3. Say vague answer ("يعني أنا بس") → Should clarify
4. Say real answer ("أنا عندي 10 سنوات خبرة") → Should advance
5. Repeat for 8 questions
6. Verify interview completes
7. Check admin dashboard shows all data
```

### Test 3: Admin Dashboard Data

```sql
-- After interview
SELECT 
    i.id,
    i.is_completed,
    i.categories_completed,
    array_length(i.asked_question_ids, 1) as questions_asked,
    s.status as scoring_status
FROM interviews i
LEFT JOIN scoring_jobs s ON s.interview_id = i.id
WHERE i.id = 'your-interview-id'
ORDER BY i.created_at DESC
LIMIT 1;

-- Expected:
-- is_completed: true
-- categories_completed: >= 6
-- questions_asked: 8
-- scoring_status: 'pending' or 'processing'
```

---

## ✅ SUCCESS CRITERIA

After implementation:

### Technical Validation
```
✅ Noise rejection rate: >95%
✅ False positive rate: <5%
✅ Answer validation accuracy: >90%
✅ Sequential question flow: 100%
✅ Admin dashboard data: 100% complete
✅ Average validation time: <500ms per answer
```

### User Experience
```
✅ Natural conversation flow
✅ Clear clarification requests
✅ No premature question advancement
✅ Proper interview completion
✅ Professional closing
```

### Business Impact
```
✅ Valid interviews: 100%
✅ Complete transcripts: 100%
✅ Accurate scoring: >90%
✅ Admin dashboard usability: High
✅ Hiring decision confidence: High
```

---

## 🚀 DEPLOYMENT SEQUENCE

1. **Deploy Enhanced Filters**: Low risk
2. **Deploy Semantic Validator**: Medium risk (LLM dependency)
3. **Deploy Flow Controller**: High risk (core logic)
4. **Update WebSocket Handler**: Critical (integration point)
5. **Deploy Admin Sync**: Low risk (post-interview)

**Total Time**: 8-10 hours
**Risk Level**: High (comprehensive overhaul)
**Rollback Plan**: Git revert ready

---

## 📊 ARCHITECTURE DIAGRAM

```
┌─────────────────────────────────────────────────────────────┐
│                   USER SPEAKS                               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              Groq Whisper STT                               │
│              (may hallucinate noise)                        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  VALIDATION PIPELINE (FlowController)                       │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────┐     │
│  │ GATE 1: Enhanced Lexical Filter                   │     │
│  │ - Pattern detection                               │     │
│  │ - Filler removal                                  │     │
│  │ - Diversity scoring                               │     │
│  └───────────────────────────────────────────────────┘     │
│                       ↓                                     │
│  ┌───────────────────────────────────────────────────┐     │
│  │ GATE 2: LLM Semantic Validator (Groq)             │     │
│  │ - Answer quality check                            │     │
│  │ - Relevance validation                            │     │
│  │ - Confidence scoring                              │     │
│  └───────────────────────────────────────────────────┘     │
│                       ↓                                     │
│  ┌───────────────────────────────────────────────────┐     │
│  │ DECISION LOGIC                                     │     │
│  │ - Valid? → Advance to next question               │     │
│  │ - Invalid? → Request clarification (max 3x)       │     │
│  │ - Complete? → Finalize interview                  │     │
│  └───────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  INTERVIEW AGENT (LangGraph)                                │
│  - Generate Sarah's response                                │
│  - Enforce Jordanian dialect                                │
│  - Maintain conversation context                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  ADMIN DASHBOARD SYNC (on complete)                         │
│  - Mark interview complete                                  │
│  - Queue scoring job                                        │
│  - Refresh dashboard view                                   │
└─────────────────────────────────────────────────────────────┘
```

---

**START IMPLEMENTATION**

Follow tasks 1-6 sequentially.
Test thoroughly after each task.
Deploy to staging before production.

**Total estimated time: 8-10 hours**

Good luck! 🚀

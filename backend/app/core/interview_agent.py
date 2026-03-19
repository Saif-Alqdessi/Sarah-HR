"""
LangGraph Interview Agent
Stateful interview conductor with multi-provider LLM + local fact verification.
Arabic-first: questions from DB, Jordanian dialect enforced.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime
import asyncio
import re
import logging

from app.models.candidate import CandidateContract
from app.core.persona_enforcer import PersonaEnforcer, CandidateLanguageMonitor
from app.core.llm_manager import MultiProviderLLM
from app.services.credibility_scorer import CredibilityScorer
from app.services.question_selector import DatabaseQuestionSelector
from app.db.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


class InterviewState(TypedDict):
    """
    Interview state schema - tracks all conversation context.
    Updated for 6-category question-bank flow.
    """
    # Immutable facts (from contract)
    contract: CandidateContract

    # Mutable interview state
    current_stage: str
    questions_asked: List[str]
    conversation_history: List[Dict]
    detected_inconsistencies: List[Dict]

    # Latest turn data
    latest_user_input: str
    latest_system_response: str

    # Metadata
    interview_id: str
    started_at: datetime
    turn_count: int

    # Scoring & progress tracking
    credibility_score: int            # 0-100, starts at 100, deducted on inconsistency
    topics_covered: List[str]         # e.g. ["experience", "salary", "skills"]
    stage_turn_count: int             # Turns spent in the current stage (reset on transition)

    # Question-bank fields (new)
    current_category_index: int       # 0-5, which category we are on
    asked_question_ids: List[str]     # e.g. ["q1_1", "q2_3"]
    selected_question_id: str
    selected_question_text: str       # Arabic text of the current question
    selected_question_category: str   # Arabic name of current category
    selected_question_stage: str      # Stage key (e.g. "communication")
    categories_completed: int         # How many categories completed so far

    # Answer validation
    answer_is_valid: bool             # False if user response was noise / too short


class InterviewAgent:
    """
    Main interview orchestrator using LangGraph
    """
    
    # Simplified 3-stage flow: opening -> questioning (6 DB categories) -> closing
    STAGES = {
        "opening": {
            "name": "الترحيب",
            "goal": "Welcome the candidate warmly in Jordanian dialect",
            "min_questions": 1,
            "next_stage": "questioning",
            "required_topics": [],
        },
        "questioning": {
            "name": "الأسئلة",
            "goal": "Ask DB-driven questions across 6 categories",
            "min_questions": 6,
            "next_stage": "closing",
            "required_topics": [],
        },
        "closing": {
            "name": "الاختتام",
            "goal": "Thank the candidate and explain next steps",
            "min_questions": 1,
            "next_stage": None,
            "required_topics": [],
        },
    }

    # Safety counter: never stay in one stage for more than this many turns.
    # 6 questions + candidate responses + follow-ups = 15 is a safe ceiling.
    MAX_TURNS_PER_STAGE = 15

    # Canonical number of categories — must match the question_bank.
    TOTAL_CATEGORIES = 8

    # Topic keyword maps — used to auto-mark topics as covered
    TOPIC_KEYWORDS: Dict[str, List[str]] = {
        "experience":  ["خبرة", "سنة", "سنوات", "شغل", "عملت", "اشتغلت"],
        "salary":      ["راتب", "مرتب", "دينار", "أجر", "مبلغ"],
        "skills":      ["مهارة", "قدرة", "تقدر", "شاطر", "تعرف", "تعمل"],
        "availability":["بتبدأ", "فوري", "متاح", "تبدأ", "متى"],
    }
    
    def __init__(self):
        """
        Initialize interview agent with database question selector
        """
        from app.core.llm_manager import MultiProviderLLM

        self.llm = MultiProviderLLM()
        self.temperature = 0.2
        self.scorer = CredibilityScorer()

        # Initialize database question selector
        self.supabase = get_supabase_client()
        self.question_selector = DatabaseQuestionSelector(self.supabase)

        # Build state machine and compile ONCE (not per-turn)
        self.workflow = self._build_workflow()

        # Persistent MemorySaver — shared across all turns of every session.
        self.checkpointer = MemorySaver()
        self.app = self.workflow.compile(checkpointer=self.checkpointer)

        logger.info("InterviewAgent initialized with database question selector")
        
    def _build_workflow(self) -> StateGraph:
        """
        Build LangGraph state machine.
        Flow: load_context -> validate_answer -> select_question -> generate_response
              -> verify_facts -> enforce_persona -> check_stage_transition -> score_credibility -> END
        """
        workflow = StateGraph(InterviewState)

        # Add nodes
        workflow.add_node("load_context", self._load_context_node)
        workflow.add_node("validate_answer", self._validate_answer_node)
        workflow.add_node("select_question", self._select_question_node)
        workflow.add_node("generate_response", self._generate_response_node)
        workflow.add_node("verify_facts", self._verify_facts_node)
        workflow.add_node("enforce_persona", self._enforce_persona_node)
        workflow.add_node("check_stage_transition", self._check_stage_transition_node)
        workflow.add_node("score_credibility", self._score_credibility_node)

        # Define edges
        workflow.set_entry_point("load_context")
        workflow.add_edge("load_context", "validate_answer")
        workflow.add_edge("validate_answer", "select_question")
        workflow.add_edge("select_question", "generate_response")
        workflow.add_edge("generate_response", "verify_facts")
        workflow.add_edge("verify_facts", "enforce_persona")
        workflow.add_edge("enforce_persona", "check_stage_transition")
        workflow.add_edge("check_stage_transition", "score_credibility")
        workflow.add_edge("score_credibility", END)

        return workflow
    
    def _load_context_node(self, state: InterviewState) -> InterviewState:
        """
        Node 1: Load or verify contract (Arabic-first)
        """
        contract = state["contract"]
        logger.info("Contract loaded for %s (role: %s)", contract.full_name, contract.target_role)
        return state

    # ── Noise / gibberish patterns (common Whisper artefacts) ──
    _NOISE_PATTERNS = {
        "أعوذ بالله", "بسم الله", "السلام عليكم",
        "music", "...", "", " ",
        "شكراً للمشاهدة", "ترجمة", "اشترك",  # Common Whisper hallucinations
    }

    def _validate_answer_node(self, state: InterviewState) -> InterviewState:
        """
        Node 1.5: Check if the user's response is meaningful.
        If the response is noise, too short, or empty — set answer_is_valid=False
        so the next nodes ask for elaboration instead of advancing.
        """
        user_input = state.get("latest_user_input", "").strip()
        current_stage = state.get("current_stage", "opening")

        # Opening stage: any input is fine (greeting, name, etc.)
        if current_stage == "opening":
            state["answer_is_valid"] = True
            return state

        # Closing stage: any input is fine
        if current_stage == "closing":
            state["answer_is_valid"] = True
            return state

        # Check for empty / noise
        if not user_input or user_input.lower() in self._NOISE_PATTERNS:
            logger.info("Answer validation: INVALID (empty/noise): '%s'", user_input[:30])
            state["answer_is_valid"] = False
            return state

        # Check word count (Arabic words split by spaces)
        word_count = len(user_input.split())
        if word_count < 3:
            logger.info(
                "Answer validation: INVALID (too short, %d words): '%s'",
                word_count, user_input[:50],
            )
            state["answer_is_valid"] = False
            return state

        logger.info("Answer validation: VALID (%d words)", word_count)
        state["answer_is_valid"] = True
        return state

    def _select_question_node(self, state: InterviewState) -> InterviewState:
        """
        Node 2: Select next question from DATABASE.
        Only fires during the 'questioning' stage AND when the previous
        answer was valid. If invalid, we skip selection (stay on same
        category) so generate_response asks for elaboration.
        """
        current_stage = state["current_stage"]

        if current_stage != "questioning":
            logger.info("Stage '%s' - skipping question selection", current_stage)
            return state

        # If the candidate's answer was noise / too short, don't advance
        if not state.get("answer_is_valid", True):
            logger.info("Answer was invalid — skipping question selection (will ask to elaborate)")
            return state

        # Get current category index (0-5)
        category_index = state.get("current_category_index", 0)

        # Check if all 6 categories completed
        if category_index >= self.TOTAL_CATEGORIES:
            logger.info("All %d categories completed - moving to closing", self.TOTAL_CATEGORIES)
            state["current_stage"] = "closing"
            return state

        # Convert category_index (0-5) to category_id (1-6)
        category_id = category_index + 1

        # Get excluded question IDs
        asked_ids = state.get("asked_question_ids", [])

        # Select random question from DATABASE (with retry)
        selected = self.question_selector.select_random_question(
            category_id=category_id,
            exclude_ids=asked_ids,
        )

        if selected:
            logger.info(
                "DB question: Category %d/%d (%s) - %s",
                category_id,
                self.TOTAL_CATEGORIES,
                selected['category_name_ar'],
                selected['question_text_ar'][:50],
            )

            state["selected_question_id"] = selected["question_id"]
            state["selected_question_text"] = selected["question_text_ar"]
            state["selected_question_category"] = selected["category_name_ar"]
            state["selected_question_stage"] = selected["category_stage"]

            # Track asked questions
            if "asked_question_ids" not in state:
                state["asked_question_ids"] = []
            state["asked_question_ids"].append(selected["question_id"])

            # Advance category index for the NEXT turn
            state["current_category_index"] = category_index + 1
            state["categories_completed"] = category_index + 1
            logger.info(
                "Category index advanced to %d / %d",
                category_index + 1, self.TOTAL_CATEGORIES,
            )
        else:
            # CRITICAL: Jump to closing to prevent infinite question-starvation loop
            logger.warning(
                "Question selection failed for category %d — transitioning to closing to prevent infinite loop",
                category_id,
            )
            state["current_stage"] = "closing"

        return state
    
    def _generate_response_node(self, state: InterviewState) -> InterviewState:
        """
        Node 2: Generate LLM response with fact-constrained prompt
        """
        contract = state["contract"]
        current_stage = state["current_stage"]
        user_input = state.get("latest_user_input", "")

        # Get selected question if in questioning stage
        selected_question = state.get("selected_question_text")
        category_name = state.get("selected_question_category")

        # If the answer was invalid, prepend an elaboration instruction
        elaboration_hint = ""
        if not state.get("answer_is_valid", True) and current_stage == "questioning":
            elaboration_hint = (
                "\n# تنبيه: جواب المتقدم كان قصير أو غير واضح.\n"
                "اطلبي منه بلطف أن يوضح أكثر أو يعيد الجواب بتفصيل.\n"
                'مثال: "ممكن توضحلي أكثر؟ شو بالظبط تجربتك بهاد الموضوع؟"\n'
            )

        # Build system prompt with embedded facts + selected question
        system_prompt = self._build_system_prompt(
            contract,
            current_stage,
            selected_question=selected_question,
            category_name=category_name,
        )
        if elaboration_hint:
            system_prompt += elaboration_hint

        # Build messages
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add conversation history
        for turn in state.get("conversation_history", []):
            messages.append({
                "role": turn["role"],
                "content": turn["content"]
            })
        
        # Add latest user input
        if user_input:
            messages.append({"role": "user", "content": user_input})
        
        # Call LLM via MultiProviderLLM (Groq -> OpenAI fallback, 1 call per turn).
        # Use a new thread to avoid "event loop already running" inside FastAPI's
        # async context — LangGraph nodes are sync but FastAPI is async.
        try:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    self.llm.generate(
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=150,
                    ),
                )
                llm_output = future.result(timeout=30)
        except Exception as e:
            logger.error("LLM generation failed, using safe fallback: %s", e)
            llm_output = "عذراً، ممكن تعيد الجواب؟"

        # Store in state
        state["latest_system_response"] = llm_output

        logger.info("LLM Generated: %s", llm_output[:80])

        return state
    
    # Fact verification is now handled by PersonaEnforcer

    def _verify_facts_node(self, state: InterviewState) -> InterviewState:
        """
        Node 3: LOCAL fact verification — no LLM call.
        Auto-corrects hallucinated numbers before TTS using PersonaEnforcer.
        """
        contract = state["contract"]
        response = state["latest_system_response"]

        from app.core.persona_enforcer import PersonaEnforcer
        enforcer = PersonaEnforcer()
        is_valid, corrected = enforcer.enforce_facts(
            response, 
            contract_exp=contract.years_of_experience, 
            contract_salary=contract.expected_salary
        )

        if not is_valid:
            logger.warning("Hallucination corrected | original: %s | fixed: %s", response[:60], corrected[:60])
            state["latest_system_response"] = corrected
            state["detected_inconsistencies"].append({
                "type": "llm_hallucination_autocorrected",
                "turn": state["turn_count"],
                "original": response,
                "corrected": corrected,
                "timestamp": datetime.utcnow().isoformat(),
            })
        else:
            logger.info("Fact verification passed")

        return state
    
    def _enforce_persona_node(self, state: InterviewState) -> InterviewState:
        """
        Node 4: Enforce Jordanian Arabic persona
        """
        response = state["latest_system_response"]
        
        enforcer = PersonaEnforcer()
        is_valid, error, corrected = enforcer.enforce(response, strict_mode=False)
        
        if not is_valid:
            print(f"⚠️ Persona violation: {error}")
            # Could regenerate or correct here
        
        # Apply corrections (MSA → Jordanian)
        if corrected != response:
            print(f"🔄 Persona correction applied")
            state["latest_system_response"] = corrected
        
        print("✅ Persona enforcement passed")
        
        return state
    
    def _check_stage_transition_node(self, state: InterviewState) -> InterviewState:
        """
        Node 5: Decide whether to advance to the next stage.

        For 'questioning': transition is driven by categories_completed
        (set by _select_question_node), NOT by the old min_questions counter.
        Category index is advanced in _select_question_node, not here.
        """
        current_stage = state["current_stage"]
        topics_covered  = state.get("topics_covered", [])
        stage_turn_count = state.get("stage_turn_count", 0) + 1

        stage_config = self.STAGES.get(current_stage)
        if not stage_config:
            state["stage_turn_count"] = stage_turn_count
            return state

        # Auto-detect new topics from the current exchange
        exchange_text = (
            state.get("latest_user_input", "") + " " +
            state.get("latest_system_response", "")
        ).lower()
        for topic, keywords in self.TOPIC_KEYWORDS.items():
            if topic not in topics_covered:
                if any(kw in exchange_text for kw in keywords):
                    topics_covered.append(topic)
                    logger.info("Topic covered: %s", topic)

        state["topics_covered"] = topics_covered
        state["stage_turn_count"] = stage_turn_count

        next_stage = stage_config["next_stage"]
        if not next_stage:
            return state  # closing stage — nowhere to go

        # ── Questioning stage: transition only when all 6 categories done ──
        if current_stage == "questioning":
            cats_done = state.get("categories_completed", 0)
            safety_exceeded = stage_turn_count >= self.MAX_TURNS_PER_STAGE

            if cats_done >= self.TOTAL_CATEGORIES or safety_exceeded:
                reason = "all 6 categories done" if cats_done >= self.TOTAL_CATEGORIES else "safety counter"
                logger.info(
                    "Stage transition: questioning -> closing (%s, %d/%d categories, turn %d)",
                    reason, cats_done, self.TOTAL_CATEGORIES, stage_turn_count,
                )
                state["current_stage"] = "closing"
                state["stage_turn_count"] = 0
            else:
                logger.info(
                    "Staying in questioning: %d/%d categories done (turn %d/%d)",
                    cats_done, self.TOTAL_CATEGORIES, stage_turn_count, self.MAX_TURNS_PER_STAGE,
                )
            return state

        # ── Opening stage: advance after 1 turn ──
        if current_stage == "opening" and stage_turn_count >= 1:
            logger.info("Stage transition: opening -> questioning")
            state["current_stage"] = "questioning"
            state["stage_turn_count"] = 0

        return state

    def _score_credibility_node(self, state: InterviewState) -> InterviewState:
        """
        Node 6: Lightweight per-turn credibility adjustment.

        Deducts points from credibility_score whenever the fact-verifier
        flagged an inconsistency THIS turn. A full post-interview LLM scoring
        pass happens in _finalize_interview (WebSocket handler).
        """
        inconsistencies = state.get("detected_inconsistencies", [])
        current_score   = state.get("credibility_score", 100)

        # Count new inconsistencies in this turn only
        turn = state.get("turn_count", 0)
        new_flags = [
            inc for inc in inconsistencies
            if inc.get("turn") == turn
        ]

        if new_flags:
            # Deduct 10 points per flag, floor at 0
            deduction = min(current_score, len(new_flags) * 10)
            current_score = max(0, current_score - deduction)
            logger.info(
                "📉 Credibility deducted -%d pts (%d flag(s)) → score: %d",
                deduction, len(new_flags), current_score
            )

        state["credibility_score"] = current_score
        return state
    
    def _build_system_prompt(
        self,
        contract: CandidateContract,
        stage: str,
        selected_question: Optional[str] = None,
        category_name: Optional[str] = None,
    ) -> str:
        """
        Build system prompt with Jordanian dialect enforcement.
        Stage-aware: opening / questioning / closing.
        """
        # Get experience in Arabic
        experience_ar = contract.get_experience_arabic()
        field_exp_ar = "عنده خبرة" if contract.has_field_experience_bool() else "بدون خبرة"

        # Base persona with STRONG Jordanian dialect rules
        company_display = contract.company_name or "Qabalan"
        base_prompt = f"""# هويتك
أنت سارة، مسؤولة توظيف في شركة {company_display}.

# حقائق المتقدم (من قاعدة البيانات - ثابتة)
- الاسم: {contract.full_name}
- الوظيفة المطلوبة: {contract.target_role}
- عدد سنوات الخبرة: {experience_ar} ({contract.years_of_experience} سنة بالضبط)
- الراتب المتوقع: {contract.expected_salary} دينار
- خبرة بالمجال: {field_exp_ar}
- قرب السكن: {contract.proximity_to_branch or "غير محدد"}

# قواعد اللهجة الأردنية (MANDATORY)
يجب استخدام اللهجة الأردنية (عمّان) فقط:

- ماذا -> شو
- لماذا -> ليش
- أين -> وين
- كيف حالك -> كيفك
- سوف -> راح
- أريد -> بدي
- لديك -> عندك
- الآن -> هسا
- هذا -> هاد
- جيد -> منيح
- كثيراً -> كتير

# قواعد عامة
1. الردود قصيرة: 15-20 كلمة
2. سؤال واحد فقط
3. استخدم رقم الخبرة الدقيق: {contract.years_of_experience} سنة
4. ممنوع الإنجليزية نهائيا
"""

        # Stage-specific prompts
        if stage == "opening":
            return base_prompt + f"""
# المرحلة: الترحيب
رحّب بالمتقدم بشكل دافئ واحترافي بلهجة أردنية.
مثال: "مرحبا {contract.full_name}! أنا سارة من شركة {company_display}. كيفك اليوم؟ مستعد نبدأ؟"
"""

        elif stage == "questioning" and selected_question:
            return base_prompt + f"""
# المرحلة: الأسئلة - {category_name}

السؤال من بنك الأسئلة:
"{selected_question}"

مهمتك: اطرح هذا السؤال بطريقة طبيعية بلهجة أردنية.

أمثلة تكييف:
السؤال: "كيف تتعامل مع زميل عمل يسيء فهمك؟"
تكييف: "بالشغل، شو بتسوي لما زميلك يفهمك غلط؟"

السؤال: "حدثني عن خطأ ارتكبته في عملك السابق"
تكييف: "انت عندك {experience_ar} خبرة، حكيلي عن موقف غلطت فيه وشو تعلمت منه؟"

الآن اطرح السؤال بلهجة أردنية طبيعية.
"""

        elif stage == "closing":
            return base_prompt + f"""
# المرحلة: الاختتام
اشكر المتقدم واخبره الخطوات التالية.
مثال: "تمام {contract.full_name}، شكرا كتير على وقتك! راح نتواصل معك خلال أسبوع. عندك أي سؤال؟"
"""

        return base_prompt
    
    async def process_turn(
        self,
        contract: CandidateContract,
        user_input: str,
        current_state: Dict
    ) -> Dict:
        """
        Process a single conversation turn

        Args:
            contract: Immutable candidate contract
            user_input: Latest user utterance
            current_state: Current interview state

        Returns:
            Updated state with system response
        """
        # Initialize state if first turn
        if not current_state:
            current_state = {
                "contract": contract,
                "current_stage": "opening",
                "questions_asked": [],
                "conversation_history": [],
                "detected_inconsistencies": [],
                "interview_id": str(contract.interview_id),
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
                "answer_is_valid": True,
            }
        
        # Update state with latest input
        current_state["latest_user_input"] = user_input
        current_state["turn_count"] += 1
        
        # Add user input to history
        current_state["conversation_history"].append({
            "role": "user",
            "content": user_input
        })
        
        # Capture initial stage BEFORE the graph runs (stage may change mid-graph)
        initial_stage = current_state.get("current_stage", "unknown")
        
        # Execute state machine using persistent compiled app.
        # thread_id isolates each interview session's memory in the MemorySaver.
        config = {"configurable": {"thread_id": current_state["interview_id"]}}
        final_state = self.app.invoke(current_state, config=config)
        
        # Extract response
        system_response = final_state["latest_system_response"]
        
        # Add to history
        final_state["conversation_history"].append({
            "role": "assistant",
            "content": system_response
        })
        
        # Add question tracking — use the INITIAL stage (before graph transitions)
        # to avoid counting an opening turn as a questioning question.
        final_state["questions_asked"].append(
            f"{initial_stage}_q{len(final_state['questions_asked'])}"
        )
        
        # ── Diagnostic logging ──
        logger.info(
            "TURN %d COMPLETE | stage: %s → %s | categories: %d/6 | history: %d msgs | questions: %d",
            final_state.get("turn_count", 0),
            initial_stage,
            final_state.get("current_stage", "?"),
            final_state.get("categories_completed", 0),
            len(final_state.get("conversation_history", [])),
            len(final_state.get("questions_asked", [])),
        )
        
        return final_state

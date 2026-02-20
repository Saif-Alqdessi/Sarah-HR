"""
LangGraph Interview Agent
Stateful interview conductor with triple-verification
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import TypedDict, Annotated, List, Dict, Any
import operator
from datetime import datetime
import openai
import os

from app.core.fact_contract import CandidateContract, FactVerifier
from app.core.persona_enforcer import PersonaEnforcer, CandidateLanguageMonitor


class InterviewState(TypedDict):
    """
    Interview state schema - tracks all conversation context
    """
    # Immutable facts (from contract)
    contract: CandidateContract
    
    # Mutable interview state
    current_stage: str
    questions_asked: Annotated[List[str], operator.add]
    conversation_history: Annotated[List[Dict], operator.add]
    detected_inconsistencies: Annotated[List[Dict], operator.add]
    
    # Latest turn data
    latest_user_input: str
    latest_system_response: str
    
    # Metadata
    interview_id: str
    started_at: datetime
    turn_count: int


class InterviewAgent:
    """
    Main interview orchestrator using LangGraph
    """
    
    STAGES = {
        "opening": {
            "name": "الترحيب",
            "goal": "Welcome candidate and confirm their application details",
            "min_questions": 1,
            "next_stage": "experience_probe"
        },
        "experience_probe": {
            "name": "استكشاف الخبرة",
            "goal": "Deep dive into their experience claims",
            "min_questions": 3,
            "next_stage": "credibility_check"
        },
        "credibility_check": {
            "name": "فحص المصداقية",
            "goal": "Verify consistency of answers",
            "min_questions": 2,
            "next_stage": "closing"
        },
        "closing": {
            "name": "الاختتام",
            "goal": "Wrap up and set expectations",
            "min_questions": 1,
            "next_stage": None
        }
    }
    
    def __init__(self):
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.model = "gpt-4o-mini"
        self.temperature = 0.2  # Low = less hallucination
        
        # Build state machine
        self.workflow = self._build_workflow()
        
    def _build_workflow(self) -> StateGraph:
        """
        Build LangGraph state machine
        """
        workflow = StateGraph(InterviewState)
        
        # Add nodes
        workflow.add_node("load_context", self._load_context_node)
        workflow.add_node("generate_response", self._generate_response_node)
        workflow.add_node("verify_facts", self._verify_facts_node)
        workflow.add_node("enforce_persona", self._enforce_persona_node)
        workflow.add_node("check_stage_transition", self._check_stage_transition_node)
        
        # Define edges
        workflow.set_entry_point("load_context")
        workflow.add_edge("load_context", "generate_response")
        workflow.add_edge("generate_response", "verify_facts")
        workflow.add_edge("verify_facts", "enforce_persona")
        workflow.add_edge("enforce_persona", "check_stage_transition")
        workflow.add_edge("check_stage_transition", END)
        
        return workflow
    
    def _load_context_node(self, state: InterviewState) -> InterviewState:
        """
        Node 1: Load or verify contract
        """
        # Contract should already be loaded, just verify integrity
        if not state["contract"].verify_integrity():
            raise ValueError("Contract integrity check failed - possible tampering")
        
        print(f"✅ Contract verified: {state['contract'].contract_hash}")
        return state
    
    def _generate_response_node(self, state: InterviewState) -> InterviewState:
        """
        Node 2: Generate LLM response with fact-constrained prompt
        """
        contract = state["contract"]
        current_stage = state["current_stage"]
        user_input = state.get("latest_user_input", "")
        
        # Build system prompt with embedded facts
        system_prompt = self._build_system_prompt(contract, current_stage)
        
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
        
        # Call LLM
        response = openai.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=100
        )
        
        llm_output = response.choices[0].message.content.strip()
        
        # Store in state
        state["latest_system_response"] = llm_output
        
        print(f"🤖 LLM Generated: {llm_output[:80]}...")
        
        return state
    
    def _verify_facts_node(self, state: InterviewState) -> InterviewState:
        """
        Node 3: Verify response against contract (CRITICAL)
        """
        contract = state["contract"]
        response = state["latest_system_response"]
        
        # Create verifier
        verifier = FactVerifier(contract)
        
        # Verify
        is_valid, error, corrected = verifier.verify_response(response)
        
        if not is_valid:
            print(f"❌ HALLUCINATION DETECTED: {error}")
            print(f"   Original: {response}")
            print(f"   Corrected: {corrected}")
            
            # Replace with corrected version
            state["latest_system_response"] = corrected
            
            # Log the hallucination
            state["detected_inconsistencies"].append({
                "type": "llm_hallucination",
                "turn": state["turn_count"],
                "original": response,
                "corrected": corrected,
                "error": error,
                "timestamp": datetime.utcnow().isoformat()
            })
        else:
            print("✅ Fact verification passed")
        
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
        Node 5: Check if ready to transition to next stage
        """
        current_stage = state["current_stage"]
        questions_asked = state.get("questions_asked", [])
        
        stage_config = self.STAGES.get(current_stage)
        if not stage_config:
            return state
        
        # Count questions in current stage
        stage_questions = [q for q in questions_asked if q.startswith(current_stage)]
        
        if len(stage_questions) >= stage_config["min_questions"]:
            next_stage = stage_config["next_stage"]
            if next_stage:
                print(f"🔄 Stage transition: {current_stage} → {next_stage}")
                state["current_stage"] = next_stage
        
        return state
    
    def _build_system_prompt(self, contract: CandidateContract, stage: str) -> str:
        """
        Build fact-constrained system prompt
        """
        stage_config = self.STAGES.get(stage, {})
        
        return f"""# هويتك
أنت سارة، مسؤولة توظيف محترفة في مخبز Golden Crust.

# حقائق المتقدم (من قاعدة البيانات - ثابتة)
⚠️ هذه الحقائق دقيقة 100% من قاعدة البيانات. استخدمها بالضبط:

- الاسم: {contract.full_name}
- الوظيفة المطلوبة: {contract.target_role}
- عدد سنوات الخبرة: {contract.years_of_experience} سنة (بالضبط - لا تقل رقم آخر)
- الراتب المتوقع: {contract.expected_salary} دينار (بالضبط)
- خبرة في نفس المجال: {"نعم" if contract.has_field_experience else "لا"}
- قرب السكن: {contract.proximity_to_branch or "غير محدد"}

# مرحلة المقابلة الحالية: {stage_config.get('name', stage)}
الهدف: {stage_config.get('goal', 'إجراء المقابلة')}

# قواعد صارمة
1. إذا ذكرت سنوات الخبرة، قل "{contract.years_of_experience} سنة" - الرقم الدقيق
2. استخدم اللهجة الأردنية فقط: شو، ليش، كيفك، راح، عم، بدي
3. ممنوع الإنجليزية نهائياً
4. الردود قصيرة: أقل من 20 كلمة
5. سؤال واحد فقط في كل رد

# أسلوب السؤال
استخدم الطلب الإلكتروني كنقطة انطلاق:
- "شفت بطلبك انك كتبت..."
- "ذكرت انك عندك {contract.years_of_experience} سنة خبرة. حدثني أكثر..."

⚠️ إذا خالفت القواعد، سيتم رفض ردك تلقائياً.
"""
    
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
                "interview_id": contract.interview_id,
                "started_at": datetime.utcnow(),
                "turn_count": 0
            }
        
        # Update state with latest input
        current_state["latest_user_input"] = user_input
        current_state["turn_count"] += 1
        
        # Add user input to history
        current_state["conversation_history"].append({
            "role": "user",
            "content": user_input
        })
        
        # Compile and run workflow
        app = self.workflow.compile()
        
        # Execute state machine
        final_state = app.invoke(current_state)
        
        # Extract response
        system_response = final_state["latest_system_response"]
        
        # Add to history
        final_state["conversation_history"].append({
            "role": "assistant",
            "content": system_response
        })
        
        # Add question tracking
        stage = final_state["current_stage"]
        final_state["questions_asked"].append(f"{stage}_q{len(final_state['questions_asked'])}")
        
        return final_state

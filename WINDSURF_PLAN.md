# 🎯 MASTER PROMPT: CONTEXT-AWARE SARAH AI IMPLEMENTATION

## 📋 MISSION OVERVIEW

Transform Sarah AI from a generic interviewer into a **context-aware, credibility-focused interviewer** that uses pre-interview registration data to conduct natural, verification-based interviews in Jordanian Arabic.

**CRITICAL SAFETY CONSTRAINTS**:
⚠️ **ABSOLUTELY DO NOT MODIFY**:
- `backend/app/services/groq_transcriber.py` ✋ WORKING PERFECTLY
- `backend/app/api/routes/transcription.py` ✋ WORKING PERFECTLY  
- Frontend WebRTC audio capture logic ✋ WORKING PERFECTLY
- Any STT/audio processing code ✋ WORKING PERFECTLY

---

## 🏗️ CURRENT ARCHITECTURE (PRESERVED)

```
Frontend WebRTC → Groq Whisper STT (ar) → Agent (gpt-4o-mini) → ElevenLabs TTS
                                              ↓
                                        Supabase DB
```

**What We're Adding**: Registration form context to the Agent layer only.

---

## 📊 BACKGROUND: THE REGISTRATION FORM

Before the voice interview, candidates fill out a detailed registration form with 25+ fields including:
- Personal info (name, age, residence, phone)
- Job preferences (position, schedule, salary expectations)
- Background (experience years, education, previous employment)
- Behavioral (prayer, smoking, grooming preferences)
- Logistics (proximity to branch, start date, relatives at company)

**This data is stored in Supabase and must be used as CONTEXT during the interview.**

---

## 🎯 NEW BEHAVIOR REQUIRED

### ❌ OLD (Generic Questions)
```
Sarah: "شو خبرتك في المخابز؟"
Candidate: "5 سنين"
Sarah: "وين اشتغلت؟"
```

### ✅ NEW (Context-Aware Verification)
```
Sarah: "شفت بطلبك انك كتبت عندك 5 سنين خبرة. حدثني أكثر، شو المهام اللي كنت تعملها بالضبط؟"
Candidate: [detailed answer]

Sarah: "وكمان ذكرت انك ساكن بلواء وادي السير. المسافة من البيت للفرع بالبيادر كيف راح تكون؟"
Candidate: [answer]
```

**Sarah must**:
- ✅ Reference form answers explicitly ("شفت بطلبك...", "ذكرت انك...")
- ✅ Dig deeper into vague form responses
- ✅ Verify consistency between form and verbal answers
- ✅ Challenge unrealistic expectations naturally
- ✅ Focus on credibility assessment (المصداقية)

---

## 📂 IMPLEMENTATION TASKS

Execute in this exact order:

---

### ✅ TASK 1: UPDATE DATABASE MODELS

**File**: `backend/app/models/candidate.py`

**Objective**: Add registration form fields to Candidate model.

#### Implementation:

```python
# backend/app/models/candidate.py

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date

class CandidateRegistrationForm(BaseModel):
    """
    Pre-interview registration form data
    Matches fields from Excel registration form
    """
    
    # Personal Information
    full_name_ar: Optional[str] = Field(None, description="الاسم الرباعي")
    detailed_residence: Optional[str] = Field(None, description="مكان السكن التفصيلي")
    date_of_birth: Optional[date] = Field(None, description="تاريخ الميلاد")
    gender: Optional[str] = Field(None, description="الجنس")
    marital_status: Optional[str] = Field(None, description="الحالة الاجتماعية")
    
    # Job Preferences
    preferred_schedule: Optional[str] = Field(None, description="نظام الدوام المفضل")
    expected_salary: Optional[str] = Field(None, description="الراتب المتوقع")
    can_start_immediately: Optional[str] = Field(None, description="إمكانية البدء فوراً")
    desired_job_title: Optional[str] = Field(None, description="المسمى الوظيفي المطلوب")
    
    # Background & Experience
    years_of_experience: Optional[str] = Field(None, description="عدد سنوات الخبرة")
    has_field_experience: Optional[str] = Field(None, description="خبرة في نفس المجال")
    academic_status: Optional[str] = Field(None, description="المسار الأكاديمي")
    previously_at_qabalan: Optional[str] = Field(None, description="عمل سابق في قبلان")
    has_relatives_at_company: Optional[str] = Field(None, description="أقارب في الشركة")
    
    # Location & Logistics
    nationality: Optional[str] = Field(None, description="الجنسية")
    age_range: Optional[str] = Field(None, description="الفئة العمرية")
    proximity_to_branch: Optional[str] = Field(None, description="قرب السكن من الفرع")
    
    # Behavioral & Cultural Fit
    prayer_regularity: Optional[str] = Field(None, description="المواظبة على الصلاة")
    is_smoker: Optional[str] = Field(None, description="التدخين")
    grooming_objection: Optional[str] = Field(None, description="مانع من تهذيب الشعر")
    social_security_issues: Optional[str] = Field(None, description="مشاكل الضمان")
    
    # Metadata
    form_submitted_at: Optional[datetime] = None
    registration_form_data: Optional[Dict[str, Any]] = None  # Complete raw form


class CandidateCreate(BaseModel):
    """
    Complete candidate creation payload including registration form
    """
    # Basic info (existing fields)
    full_name: str
    phone_number: str
    email: Optional[str] = None
    target_role: str
    
    # NEW: Registration form data
    registration_form: Optional[CandidateRegistrationForm] = None


class CandidateResponse(BaseModel):
    """
    Candidate data returned to frontend
    """
    id: str
    full_name: str
    phone_number: str
    email: Optional[str]
    target_role: str
    
    # Registration context
    registration_form: Optional[CandidateRegistrationForm]
    
    # Interview tracking
    interview_status: Optional[str]
    latest_score: Optional[int]
    
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
```

---

### ✅ TASK 2: UPDATE INTELLIGENT AGENT FOR CONTEXT AWARENESS

**File**: `backend/app/services/intelligent_agent.py`

**Objective**: Make Sarah reference and verify registration form data during interview.

#### Key Changes:

1. **Accept registration form context as input**
2. **Generate context-aware questions**
3. **Track form vs interview inconsistencies**

#### Implementation:

```python
# backend/app/services/intelligent_agent.py

# Add this to the IntelligentHRAgent class:

def _build_context_aware_system_prompt(
    self,
    candidate_name: str,
    target_role: str,
    registration_form: Dict[str, Any],
    current_stage: str = "opening",
    questions_asked: List[str] = []
) -> str:
    """
    Build context-aware system prompt that references registration form
    """
    
    # Extract key registration data
    experience_years = registration_form.get("years_of_experience", "غير محدد")
    has_field_exp = registration_form.get("has_field_experience", "غير محدد")
    expected_salary = registration_form.get("expected_salary", "غير محدد")
    proximity = registration_form.get("proximity_to_branch", "غير محدد")
    academic_status = registration_form.get("academic_status", "غير محدد")
    can_start_immediately = registration_form.get("can_start_immediately", "غير محدد")
    prayer_regularity = registration_form.get("prayer_regularity", "غير محدد")
    is_smoker = registration_form.get("is_smoker", "غير محدد")
    
    return f"""# هويتك
أنت سارة، مسؤولة توظيف محترفة في مخبز Golden Crust.

# معلومات المتقدم
الاسم: {candidate_name}
الوظيفة المطلوبة: {target_role}

# بيانات الطلب الإلكتروني (استخدميها كسياق)

المتقدم سبق وعبّى طلب توظيف إلكتروني قبل المقابلة. هذه أهم المعلومات:

## الخبرة والمؤهلات
- عدد سنوات الخبرة: {experience_years}
- خبرة في نفس المجال: {has_field_exp}
- المسار الأكاديمي: {academic_status}

## التوقعات والمتطلبات
- الراتب المتوقع: {expected_salary}
- إمكانية البدء فوراً: {can_start_immediately}

## اللوجستيات
- قرب السكن من الفرع: {proximity}

## السلوكيات
- المواظبة على الصلاة: {prayer_regularity}
- التدخين: {is_smoker}

# استراتيجية المقابلة

## القاعدة الذهبية: الإشارة للطلب وطلب التفاصيل
❌ لا تكرري الأسئلة اللي موجودة بالطلب
✅ استخدمي الطلب كنقطة انطلاق للتعمق

### أمثلة على الأسلوب الصحيح:

**عن الخبرة:**
- "شفت بطلبك انك كتبت عندك {experience_years} سنين خبرة. حدثني أكثر، شو المهام اللي كنت مسؤول عنها؟"
- "ذكرت انك {has_field_exp} خبرة بنفس المجال. طيب، شو أصعب شي واجهك بهالشغل؟"

**عن الراتب:**
- "شفت انك متوقع راتب {expected_salary}. حسب خبرتك، شو اللي بخليك تستاهل هالمبلغ؟"
- "الراتب اللي كتبته بالطلب {expected_salary}. هذا قابل للتفاوض؟"

**عن المسافة:**
- "ذكرت انك ساكن {proximity}. راح تقدر تلتزم بمواعيد الشغل حتى لو الدوام الصباحي الباكر؟"

**عن البدء الفوري:**
- "كتبت انك {can_start_immediately}. يعني لو قبلناك اليوم، متى تقدر تبدأ بالضبط؟"

## القاعدة الثانية: تحري المصداقية
راقبي أي تناقضات بين الطلب والمقابلة:

**مثال 1 - تناقض بالخبرة:**
- الطلب: "5 سنين خبرة"
- المقابلة: "أول مرة بشتغل بمخبز"
→ **علامة استفهام**: اسألي بلطف: "بس انت كتبت بالطلب عندك 5 سنين خبرة، كيف هيك؟"

**مثال 2 - تناقض بالراتب:**
- الطلب: "300 دينار"
- المقابلة: "ما بقبل أقل من 500"
→ **علامة استفهام**: "لاحظت انك كتبت بالطلب 300، بس الآن عم تحكي 500. شو اللي غيّر؟"

**مثال 3 - تناقض بالالتزام:**
- الطلب: "نعم استطيع البدء فوراً"
- المقابلة: "بدي أسبوعين إجازة"
→ **علامة استفهام**: "كتبت انك تقدر تبدأ فوراً، بس الآن عم تحكي محتاج أسبوعين؟"

## القاعدة الثالثة: الأسئلة التحقيقية

### بدل السؤال المباشر:
❌ "شو خبرتك؟"
✅ "شفت انك كتبت {experience_years} خبرة. حدثني عن أصعب موقف واجهك بالشغل."

### بدل السؤال العام:
❌ "ليش مهتم بهالوظيفة؟"
✅ "ذكرت انك تبحث عن {target_role}. شو اللي بجذبك بالذات لهالمنصب؟"

## القاعدة الرابعة: طول الرد (أقل من 20 كلمة)
- اعتراف قصير (3-5 كلمات)
- إشارة لبيانات الطلب
- سؤال تحقيقي واحد
- توقف

**مثال:**
"ممتاز! شفت بطلبك انك ذكرت {experience_years} خبرة. شو نوع الخبز اللي كنت تسويه؟"
[18 كلمة - مثالي]

## القاعدة الخامسة: اللغة الأردنية الطبيعية
- "شو" بدل "ما"
- "كيف" بدل "كيف حالك"  
- "ليش" بدل "لماذا"
- "راح" بدل "سوف"
- "عم تحكي" بدل "تقول"

# مراحل المقابلة

## المرحلة 1: الترحيب والتأكيد
"مرحباً {candidate_name}! أنا سارة من مخبز Golden Crust. قبل ما نبدأ، بس بدي أتأكد - الطلب اللي عبيته صح؟ كل المعلومات سليمة؟"
[انتظري التأكيد]

## المرحلة 2: التحقق من الخبرة والمؤهلات
- استخدمي بيانات {experience_years} و {has_field_exp}
- اسألي أسئلة تحقيقية عن تفاصيل الخبرة
- دقّقي بالمهام المحددة والإنجازات

## المرحلة 3: التحقق من التوقعات الواقعية
- استخدمي {expected_salary}
- اسألي عن مبررات الراتب المتوقع
- تحققي من واقعية التوقعات

## المرحلة 4: التحقق من الجدية والالتزام
- استخدمي {can_start_immediately} و {proximity}
- تأكدي من إمكانية الالتزام بالمواعيد
- اسألي عن خطط طويلة الأجل

## المرحلة 5: الاختتام
"تمام يا {candidate_name}! شكراً على وقتك. راح نراجع ملفك ونتواصل معك خلال 48 ساعة."

# هدفك الأساسي
إجراء مقابلة تحقيقية طبيعية تركز على:
1. ✅ التحقق من صحة بيانات الطلب
2. ✅ التعمق في الإجابات السطحية
3. ✅ كشف أي تناقضات بلطف
4. ✅ تقييم المصداقية والجدية
5. ✅ الشعور بأنك راجعتي الطلب فعلاً (مش أول مرة تسمعي عنه)"""


def generate_response(
    self,
    candidate_name: str,
    target_role: str,
    conversation_history: List[Dict[str, str]],
    candidate_id: str,
    registration_form: Dict[str, Any] = None,  # NEW PARAMETER
    candidate_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate context-aware response that references registration form
    """
    
    if registration_form is None:
        registration_form = {}
    
    # Get interview state
    interview_state = self.interview_states.get(candidate_id, {
        "current_stage": "opening",
        "questions_asked": [],
        "detected_inconsistencies": []
    })
    
    # Build context-aware system prompt
    system_prompt = self._build_context_aware_system_prompt(
        candidate_name=candidate_name,
        target_role=target_role,
        registration_form=registration_form,
        current_stage=interview_state["current_stage"],
        questions_asked=interview_state["questions_asked"]
    )
    
    # Format messages
    messages = self._format_messages_for_gpt(
        system_prompt=system_prompt,
        conversation_history=conversation_history
    )
    
    # Call GPT-4o-mini
    try:
        response = openai.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature
        )
        
        intelligent_response = response.choices[0].message.content.strip()
        
        # Detect inconsistencies in real-time
        inconsistency = self._detect_inconsistency(
            conversation_history=conversation_history,
            registration_form=registration_form
        )
        
        if inconsistency:
            interview_state["detected_inconsistencies"].append(inconsistency)
        
        # Update state
        self.interview_states[candidate_id] = interview_state
        
        return {
            "response": intelligent_response,
            "current_stage": interview_state["current_stage"],
            "detected_inconsistencies": interview_state["detected_inconsistencies"]
        }
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return {
            "response": "عذراً، حدث خطأ. ممكن تعيد الجواب؟",
            "current_stage": interview_state["current_stage"]
        }


def _detect_inconsistency(
    self,
    conversation_history: List[Dict[str, str]],
    registration_form: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Detect inconsistencies between form and interview answers
    Returns inconsistency object or None
    """
    
    if not conversation_history or not registration_form:
        return None
    
    # Get last user response
    last_user_msg = None
    for msg in reversed(conversation_history):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break
    
    if not last_user_msg:
        return None
    
    # Check for common inconsistencies
    
    # 1. Experience inconsistency
    form_experience = registration_form.get("years_of_experience", "")
    if form_experience and "سن" in form_experience:
        if any(phrase in last_user_msg for phrase in ["أول مرة", "ما عندي خبرة", "مبتدئ"]):
            return {
                "type": "experience_mismatch",
                "form_value": form_experience,
                "interview_value": last_user_msg,
                "severity": "high",
                "description": "تناقض في سنوات الخبرة"
            }
    
    # 2. Salary inconsistency
    form_salary = registration_form.get("expected_salary", "")
    if form_salary:
        # Extract numbers from both form and interview
        import re
        form_numbers = re.findall(r'\d+', form_salary)
        interview_numbers = re.findall(r'\d+', last_user_msg)
        
        if form_numbers and interview_numbers:
            form_min = int(form_numbers[0])
            interview_min = int(interview_numbers[0])
            
            # If interview salary is 50% higher than form salary
            if interview_min > form_min * 1.5:
                return {
                    "type": "salary_mismatch",
                    "form_value": form_salary,
                    "interview_value": last_user_msg,
                    "severity": "medium",
                    "description": "تناقض كبير في توقعات الراتب"
                }
    
    # 3. Immediate start inconsistency
    form_start = registration_form.get("can_start_immediately", "")
    if "نعم" in form_start or "فوراً" in form_start:
        if any(phrase in last_user_msg for phrase in ["محتاج وقت", "أسبوع", "شهر", "إجازة"]):
            return {
                "type": "start_date_mismatch",
                "form_value": form_start,
                "interview_value": last_user_msg,
                "severity": "medium",
                "description": "تناقض في إمكانية البدء الفوري"
            }
    
    return None
```

---

### ✅ TASK 3: CREATE CREDIBILITY SCORING ENGINE

**File**: `backend/app/services/credibility_scorer.py` (NEW FILE)

**Objective**: Compare form answers vs interview answers and generate credibility score.

#### Implementation:

```python
# backend/app/services/credibility_scorer.py

import openai
import os
from typing import Dict, List, Any
import json

class CredibilityScorer:
    """
    Compares registration form answers with interview transcript
    to assess candidate credibility (المصداقية)
    """
    
    def __init__(self):
        self.model = "gpt-4o-mini"
        openai.api_key = os.getenv("OPENAI_API_KEY")
    
    def score_credibility(
        self,
        registration_form: Dict[str, Any],
        transcript: List[Dict[str, str]],
        detected_inconsistencies: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive credibility assessment
        
        Returns:
            {
                "credibility_score": 85,  # 0-100
                "credibility_level": "عالية",  # عالية/متوسطة/منخفضة
                "inconsistencies_found": [...],
                "consistency_areas": [...],
                "red_flags": [...],
                "recommendation": "موثوق"
            }
        """
        
        # Format data for analysis
        form_summary = self._format_form_data(registration_form)
        transcript_text = self._format_transcript(transcript)
        
        # Build scoring prompt
        scoring_prompt = f"""أنت خبير في تقييم مصداقية المتقدمين للوظائف.

# بيانات الطلب الإلكتروني (ما كتبه المتقدم)
{form_summary}

# نص المقابلة الصوتية (ما قاله المتقدم)
{transcript_text}

# التناقضات المكتشفة آلياً
{json.dumps(detected_inconsistencies or [], ensure_ascii=False, indent=2)}

# مهمتك
قارن بين ما كتبه المتقدم بالطلب وما قاله بالمقابلة. قيّم المصداقية بناءً على:

1. **الاتساق**: هل المعلومات متطابقة؟
2. **التفاصيل**: هل التفاصيل بالمقابلة تدعم ما كُتب بالطلب؟
3. **الواقعية**: هل التوقعات واقعية ومنطقية؟
4. **الصراحة**: هل المتقدم صريح أم يحاول إخفاء شيء؟

أعطِ رد JSON فقط:

{{
  "credibility_score": 85,
  "credibility_level": "عالية",
  "inconsistencies_found": [
    {{
      "area": "سنوات الخبرة",
      "form_answer": "5 سنين",
      "interview_answer": "أول مرة بشتغل",
      "severity": "عالية",
      "explanation": "تناقض واضح بين الخبرة المكتوبة والمذكورة"
    }}
  ],
  "consistency_areas": [
    "الراتب المتوقع",
    "مكان السكن",
    "المؤهل الأكاديمي"
  ],
  "red_flags": [
    "مبالغة في سنوات الخبرة",
    "عدم وضوح في التفاصيل"
  ],
  "recommendation": "يحتاج تحقق إضافي"
}}

معايير الدرجة:
- 90-100: مصداقية عالية جداً
- 75-89: مصداقية عالية
- 60-74: مصداقية متوسطة
- 40-59: مصداقية منخفضة
- 0-39: مصداقية منخفضة جداً"""

        try:
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "أنت خبير تقييم مصداقية. أعطِ JSON فقط."},
                    {"role": "user", "content": scoring_prompt}
                ],
                max_tokens=1000,
                temperature=0.2
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Clean response
            if response_text.startswith("```json"):
                response_text = response_text.replace("```json", "").replace("```", "").strip()
            elif response_text.startswith("```"):
                response_text = response_text.replace("```", "").strip()
            
            credibility_data = json.loads(response_text)
            
            return credibility_data
            
        except Exception as e:
            print(f"❌ Credibility scoring error: {str(e)}")
            return self._get_default_credibility_score()
    
    def _format_form_data(self, form: Dict[str, Any]) -> str:
        """Format registration form for display"""
        lines = []
        for key, value in form.items():
            if value:
                lines.append(f"- {key}: {value}")
        return "\n".join(lines)
    
    def _format_transcript(self, transcript: List[Dict[str, str]]) -> str:
        """Format transcript for analysis"""
        lines = []
        for turn in transcript:
            role = "سارة" if turn.get("role") == "assistant" else "المتقدم"
            content = turn.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
    
    def _get_default_credibility_score(self) -> Dict:
        """Return default score on error"""
        return {
            "credibility_score": 50,
            "credibility_level": "غير محدد",
            "inconsistencies_found": [],
            "consistency_areas": [],
            "red_flags": ["فشل التقييم التلقائي"],
            "recommendation": "يحتاج مراجعة يدوية"
        }
```

---

### ✅ TASK 4: UPDATE API ROUTES

**File**: `backend/app/api/routes/agent.py`

**Objective**: Pass registration form context to agent and save credibility scores.

#### Key Changes:

```python
# backend/app/api/routes/agent.py

# Update the handle_agent_request function to fetch and pass registration form

@router.post("/agent-response")
async def handle_agent_request(request: Request):
    """
    Generate intelligent response with registration form context
    """
    
    # ... existing code to extract candidate_id ...
    
    # NEW: Fetch registration form from database
    registration_form = {}
    try:
        result = supabase.table("candidates").select(
            "full_name_ar, years_of_experience, expected_salary, "
            "has_field_experience, proximity_to_branch, academic_status, "
            "can_start_immediately, prayer_regularity, is_smoker, "
            "registration_form_data"
        ).eq("id", candidate_id).execute()
        
        if result.data and len(result.data) > 0:
            registration_form = {
                k: v for k, v in result.data[0].items() 
                if v is not None
            }
            print(f"✅ Loaded registration form context")
    except Exception as e:
        print(f"⚠️ Could not load registration form: {str(e)}")
    
    # Call agent with registration form context
    intelligent_response = agent.generate_response(
        candidate_name=candidate_name,
        target_role=target_role,
        conversation_history=conversation_history,
        candidate_id=candidate_id,
        registration_form=registration_form,  # NEW
        candidate_context=candidate_context
    )
    
    # Return response with inconsistencies
    return JSONResponse({
        "assistant": {
            "say": intelligent_response["response"]
        },
        "current_stage": intelligent_response.get("current_stage"),
        "detected_inconsistencies": intelligent_response.get("detected_inconsistencies", [])
    })


# Update end-of-call webhook to include credibility scoring

@router.post("/vapi-webhook")
async def handle_end_of_call(request: Request, background_tasks: BackgroundTasks):
    """
    Handle end-of-call with credibility assessment
    """
    
    # ... existing code ...
    
    # NEW: Add credibility scoring task
    background_tasks.add_task(
        save_evaluation_with_credibility,
        candidate_id=candidate_id,
        target_role=target_role,
        conversation_history=conversation_history,
        detected_inconsistencies=detected_inconsistencies,
        call_data=call_data
    )
    
    return JSONResponse({"status": "accepted"})


async def save_evaluation_with_credibility(
    candidate_id: str,
    target_role: str,
    conversation_history: List[Dict],
    detected_inconsistencies: List[Dict],
    call_data: Dict
):
    """
    Save evaluation including credibility assessment
    """
    
    from app.services.credibility_scorer import CredibilityScorer
    
    try:
        # Fetch registration form
        result = supabase.table("candidates").select("*").eq(
            "id", candidate_id
        ).execute()
        
        registration_form = {}
        if result.data:
            registration_form = result.data[0]
        
        # Score credibility
        credibility_scorer = CredibilityScorer()
        credibility_data = credibility_scorer.score_credibility(
            registration_form=registration_form,
            transcript=conversation_history,
            detected_inconsistencies=detected_inconsistencies
        )
        
        print(f"✅ Credibility score: {credibility_data.get('credibility_score')}/100")
        
        # Save to scores table
        # ... existing scoring code ...
        
        # Add credibility data
        score_data["credibility_score"] = credibility_data.get("credibility_score")
        score_data["credibility_level"] = credibility_data.get("credibility_level")
        score_data["credibility_assessment"] = credibility_data
        
        # Save inconsistencies to candidates table
        if credibility_data.get("inconsistencies_found"):
            supabase.table("candidates").update({
                "credibility_flags": credibility_data["inconsistencies_found"]
            }).eq("id", candidate_id).execute()
        
    except Exception as e:
        print(f"❌ Error in credibility scoring: {str(e)}")
```

---

### ✅ TASK 5: UPDATE FRONTEND TO DISPLAY CONTEXT

**File**: `frontend/app/interview/[candidateId]/page.tsx`

**Objective**: Show candidate's registration summary during interview for HR reference.

#### Implementation:

```tsx
// frontend/app/interview/[candidateId]/page.tsx

// Add new component to display registration context
const RegistrationContextPanel = ({ 
  registrationForm 
}: { 
  registrationForm: any 
}) => {
  if (!registrationForm) return null;
  
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
      <h3 className="text-sm font-semibold text-blue-800 mb-3">
        📋 بيانات الطلب الإلكتروني
      </h3>
      
      <div className="grid grid-cols-2 gap-3 text-sm">
        {registrationForm.years_of_experience && (
          <div>
            <span className="text-gray-600">الخبرة:</span>{' '}
            <span className="font-medium">{registrationForm.years_of_experience}</span>
          </div>
        )}
        
        {registrationForm.expected_salary && (
          <div>
            <span className="text-gray-600">الراتب المتوقع:</span>{' '}
            <span className="font-medium">{registrationForm.expected_salary}</span>
          </div>
        )}
        
        {registrationForm.proximity_to_branch && (
          <div className="col-span-2">
            <span className="text-gray-600">قرب السكن:</span>{' '}
            <span className="font-medium">{registrationForm.proximity_to_branch}</span>
          </div>
        )}
        
        {registrationForm.has_field_experience && (
          <div>
            <span className="text-gray-600">خبرة بالمجال:</span>{' '}
            <span className="font-medium">{registrationForm.has_field_experience}</span>
          </div>
        )}
        
        {registrationForm.can_start_immediately && (
          <div>
            <span className="text-gray-600">البدء فوراً:</span>{' '}
            <span className="font-medium">{registrationForm.can_start_immediately}</span>
          </div>
        )}
      </div>
      
      <div className="mt-3 text-xs text-blue-700">
        💡 سارة ستشير لهذه البيانات أثناء المقابلة
      </div>
    </div>
  );
};

// Add to main interview page
return (
  <div className="min-h-screen bg-gray-50 p-6">
    <div className="max-w-4xl mx-auto">
      {/* Registration Context Panel */}
      <RegistrationContextPanel 
        registrationForm={candidate?.registration_form} 
      />
      
      {/* Rest of interview UI */}
      {/* ... */}
    </div>
  </div>
);
```

---

## 📋 IMPLEMENTATION CHECKLIST

Execute in this exact order:

### Phase 1: Database (Day 1)
- [ ] Run SQL migration in Supabase SQL Editor
- [ ] Verify all columns were added successfully
- [ ] Test inserting sample registration data

### Phase 2: Backend Models & Logic (Day 1-2)
- [ ] Update `models/candidate.py` with registration form fields
- [ ] Update `intelligent_agent.py` with context-aware prompts
- [ ] Create `credibility_scorer.py` for form vs interview comparison
- [ ] Test agent locally with mock registration data

### Phase 3: API Integration (Day 2)
- [ ] Update `api/routes/agent.py` to fetch and pass registration context
- [ ] Update webhook handler to save credibility scores
- [ ] Test full flow: form → agent → scoring → DB

### Phase 4: Frontend Display (Day 3)
- [ ] Add `RegistrationContextPanel` component
- [ ] Fetch and display registration data during interview
- [ ] Test UI updates

### Phase 5: End-to-End Testing (Day 3-4)
- [ ] Test complete interview with registration context
- [ ] Verify Sarah references form data in questions
- [ ] Check credibility scores are calculated correctly
- [ ] Test inconsistency detection
- [ ] Validate scoring data in Supabase

---

## 🎯 SUCCESS CRITERIA

The implementation is successful when:

1. ✅ Sarah explicitly references registration form in questions
2. ✅ Sarah says things like "شفت بطلبك انك..." naturally
3. ✅ Credibility score is calculated comparing form vs interview
4. ✅ Inconsistencies are flagged and stored in database
5. ✅ Frontend shows registration summary during interview
6. ✅ HR can see credibility assessment in dashboard
7. ✅ No changes to Groq Whisper or audio capture code

---

## 🚀 TESTING SCRIPTS

### Test 1: Agent Context Awareness

```python
# backend/test_context_aware_agent.py

from app.services.intelligent_agent import IntelligentHRAgent

agent = IntelligentHRAgent()

# Mock registration form
registration_form = {
    "years_of_experience": "5 سنين",
    "expected_salary": "300 دينار",
    "has_field_experience": "نعم",
    "proximity_to_branch": "قريب ومشياً"
}

# Simulate conversation
conversation = [
    {"role": "assistant", "content": "مرحباً أحمد! جاهز نبدأ؟"},
    {"role": "user", "content": "أيوه"}
]

response = agent.generate_response(
    candidate_name="أحمد",
    target_role="خباز",
    conversation_history=conversation,
    candidate_id="test-123",
    registration_form=registration_form
)

print("Response:", response["response"])
# Should contain reference to form data like "شفت بطلبك انك كتبت..."
```

### Test 2: Credibility Detection

```python
# backend/test_credibility.py

from app.services.credibility_scorer import CredibilityScorer

scorer = CredibilityScorer()

# Mock inconsistent data
registration_form = {
    "years_of_experience": "5 سنين",
    "expected_salary": "300 دينار"
}

transcript = [
    {"role": "assistant", "content": "شفت انك كتبت عندك 5 سنين خبرة. حدثني أكثر؟"},
    {"role": "user", "content": "صراحة أول مرة بشتغل بمخبز"}
]

result = scorer.score_credibility(
    registration_form=registration_form,
    transcript=transcript
)

print(f"Credibility Score: {result['credibility_score']}/100")
print(f"Inconsistencies: {result['inconsistencies_found']}")
```

---

## ⚠️ CRITICAL REMINDERS

1. **DO NOT TOUCH** `groq_transcriber.py` - STT is working perfectly
2. **DO NOT TOUCH** audio capture code - WebRTC is working perfectly
3. **PRESERVE** existing conversation flow - only add context layer
4. **TEST INCREMENTALLY** - verify each phase before moving to next
5. **BACKUP DATABASE** before running migration

---

**END OF MASTER PROMPT**

Execute these tasks sequentially and Sarah will become a context-aware, credibility-focused interviewer! 🎯

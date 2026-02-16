"""
Intelligent HR Agent - Context-Aware Interview Conductor
Provides context-aware responses that reference candidate's registration form data
"""

import openai
import os
from typing import List, Dict, Any, Optional

class IntelligentHRAgent:
    """
    Context-aware interviewer that references registration form data
    """
    
    def __init__(self):
        self.model = "gpt-4o-mini"
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.max_tokens = 80  # Keep responses concise (20 words max)
        self.temperature = 0.7
        self.interview_states = {}  # Track state per candidate
    
    def generate_response(
        self,
        candidate_name: str,
        target_role: str,
        conversation_history: List[Dict[str, str]],
        candidate_id: str,
        registration_form: Dict[str, Any] = None,
        candidate_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate context-aware response that references registration form
        
        Args:
            candidate_name: Candidate's name
            target_role: Desired position
            conversation_history: Previous messages
            candidate_id: Unique ID for state tracking
            registration_form: Pre-interview registration data (NEW)
            candidate_context: Additional context
        
        Returns:
            {
                "response": "شفت بطلبك انك...",
                "current_stage": "communication",
                "detected_inconsistencies": [...]
            }
        """
        
        if registration_form is None:
            registration_form = {}
        
        # Get or initialize interview state
        interview_state = self.interview_states.get(candidate_id, {
            "current_stage": "opening",
            "questions_asked": [],
            "detected_inconsistencies": []
        })
        
        # Build context-aware system prompt
        system_prompt = self._build_context_aware_prompt(
            candidate_name=candidate_name,
            target_role=target_role,
            registration_form=registration_form
        )
        
        # Format messages for GPT
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add conversation history
        for turn in conversation_history:
            messages.append({
                "role": turn.get("role", "user"),
                "content": turn.get("content", "")
            })
        
        # Call OpenAI
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
            
            # Save state
            self.interview_states[candidate_id] = interview_state
            
            return {
                "response": intelligent_response,
                "current_stage": interview_state["current_stage"],
                "detected_inconsistencies": interview_state["detected_inconsistencies"]
            }
            
        except Exception as e:
            print(f"❌ Error in generate_response: {str(e)}")
            return {
                "response": "عذراً، حدث خطأ. ممكن تعيد الجواب؟",
                "current_stage": interview_state["current_stage"],
                "detected_inconsistencies": interview_state.get("detected_inconsistencies", [])
            }
    
    def _build_context_aware_prompt(
        self,
        candidate_name: str,
        target_role: str,
        registration_form: Dict[str, Any]
    ) -> str:
        """
        Build context-aware system prompt that references registration form
        """
        
        # Extract key registration data
        experience_years = registration_form.get("years_of_experience", "غير محدد")
        expected_salary = registration_form.get("expected_salary", "غير محدد")
        has_field_exp = registration_form.get("has_field_experience", "غير محدد")
        proximity = registration_form.get("proximity_to_branch", "غير محدد")
        academic_status = registration_form.get("academic_status", "غير محدد")
        can_start_immediately = registration_form.get("can_start_immediately", "غير محدد")
        prayer_regularity = registration_form.get("prayer_regularity", "غير محدد")
        is_smoker = registration_form.get("is_smoker", "غير محدد")
        
        return f"""# هويتك
أنت سارة، مسؤولة توظيف محترفة وودودة في مخبز Golden Crust.

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
"شفت بطلبك انك كتبت عندك {experience_years} خبرة. حدثني أكثر، شو المهام اللي كنت مسؤول عنها؟"
"ذكرت انك {has_field_exp} خبرة بنفس المجال. طيب، شو أصعب شي واجهك بهالشغل؟"

**عن الراتب:**
"شفت انك متوقع راتب {expected_salary}. حسب خبرتك، شو اللي بخليك تستاهل هالمبلغ؟"
"الراتب اللي كتبته بالطلب {expected_salary}. هذا قابل للتفاوض؟"

**عن المسافة:**
"ذكرت انك ساكن {proximity}. راح تقدر تلتزم بمواعيد الشغل حتى لو الدوام الصباحي الباكر؟"

**عن البدء الفوري:**
"كتبت انك {can_start_immediately}. يعني لو قبلناك اليوم، متى تقدر تبدأ بالضبط؟"

## القاعدة الثانية: تحري المصداقية

راقبي أي تناقضات بين الطلب والمقابلة:

**مثال 1 - تناقض بالخبرة:**
- الطلب: "{experience_years}"
- المقابلة: "أول مرة بشتغل بمخبز"
→ **علامة استفهام**: اسألي بلطف: "بس انت كتبت بالطلب عندك {experience_years}، كيف هيك؟"

**مثال 2 - تناقض بالراتب:**
- الطلب: "{expected_salary}"
- المقابلة: "ما بقبل أقل من 500"
→ **علامة استفهام**: "لاحظت انك كتبت بالطلب {expected_salary}، بس الآن عم تحكي أكثر. شو اللي غيّر؟"

**مثال 3 - تناقض بالالتزام:**
- الطلب: "{can_start_immediately}"
- المقابلة: "بدي أسبوعين إجازة"
→ **علامة استفهام**: "كتبت انك تقدر تبدأ فوراً، بس الآن عم تحكي محتاج أسبوعين؟"

## القاعدة الثالثة: طول الرد (أقل من 20 كلمة)

- اعتراف قصير (3-5 كلمات)
- إشارة لبيانات الطلب
- سؤال تحقيقي واحد
- توقف

**مثال:**
"ممتاز! شفت بطلبك انك ذكرت {experience_years} خبرة. شو نوع الخبز اللي كنت تسويه؟"
[18 كلمة - مثالي]

## القاعدة الرابعة: اللغة الأردنية الطبيعية

- "شو" بدل "ماذا"
- "كيف" بدل "كيف حالك"
- "ليش" بدل "لماذا"
- "راح" بدل "سوف"
- "عم تحكي" بدل "تقول"

# مراحل المقابلة

## المرحلة 1: الترحيب والتأكيد
"مرحباً {candidate_name}! أنا سارة من مخبز Golden Crust. قبل ما نبدأ، بس بدي أتأكد - الطلب اللي عبيته صح؟ كل المعلومات سليمة؟"

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
    
    def _detect_inconsistency(
        self,
        conversation_history: List[Dict],
        registration_form: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Detect inconsistencies between form and interview answers
        
        Returns:
            Inconsistency dict or None
        """
        if not conversation_history or not registration_form:
            return None
        
        # Get last user message
        last_user_msg = ""
        for msg in reversed(conversation_history):
            if msg.get("role") == "user":
                last_user_msg = msg.get("content", "").lower()
                break
        
        if not last_user_msg:
            return None
        
        # Check for experience inconsistency
        form_exp = str(registration_form.get("years_of_experience", "")).lower()
        if form_exp and any(str(n) in form_exp for n in range(1, 20)):
            if any(phrase in last_user_msg for phrase in ["أول مرة", "ما عندي خبرة", "مبتدئ", "بدون خبرة"]):
                return {
                    "type": "experience_mismatch",
                    "form_value": form_exp,
                    "interview_value": last_user_msg,
                    "severity": "high",
                    "description": "تناقض في سنوات الخبرة"
                }
        
        # Check for salary inconsistency
        form_salary = str(registration_form.get("expected_salary", ""))
        if form_salary:
            import re
            form_numbers = re.findall(r'\d+', form_salary)
            interview_numbers = re.findall(r'\d+', last_user_msg)
            
            if form_numbers and interview_numbers:
                form_min = int(form_numbers[0])
                interview_min = int(interview_numbers[0])
                
                # If interview salary is 50%+ higher
                if interview_min > form_min * 1.5:
                    return {
                        "type": "salary_mismatch",
                        "form_value": form_salary,
                        "interview_value": last_user_msg,
                        "severity": "medium",
                        "description": "تناقض كبير في توقعات الراتب"
                    }
        
        # Check for immediate start inconsistency
        form_start = str(registration_form.get("can_start_immediately", "")).lower()
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
# -*- coding: utf-8 -*-
"""
Intelligent HR Agent using Groq (Llama-3.3) for contextual interview reasoning.
Acts as Sarah's brain - makes all interviewing decisions with warmth and empathy.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from openai import OpenAI
from app.config import settings

# إعداد Groq كبديل مجاني وسريع لـ OpenAI
# بدلاً من الكود القديم، استخدم كائن settings الذي استوردته في السطر 13
client = OpenAI(
    api_key=settings.groq_api_key,
    base_url=settings.openai_api_base
)


class IntelligentHRAgent:
    """
    Intelligent HR Agent using Groq Llama-3.3 for reasoning.
    Acts as Sarah's brain - makes all interviewing decisions.
    """

    def __init__(self) -> None:
        # قمنا بتغيير الموديل إلى أقوى موديل متاح مجاناً في Groq حالياً
        self.model = "llama-3.1-8b-instant" 
        self.max_tokens = 150 # رفعنا التوكنز قليلاً لضمان عدم قص الرد العربي
        self.temperature = 0.7
        self.interview_states: Dict[str, Dict[str, Any]] = {}

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
        candidate_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate intelligent response based on conversation context using Groq.
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

        messages = self._format_messages_for_gpt(
            system_prompt=system_prompt,
            conversation_history=conversation_history,
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            intelligent_response = response.choices[0].message.content or ""
            intelligent_response = intelligent_response.strip()
            
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
            print(f"❌ Error generating response via Groq: {str(e)}")
            return {
                "response": "عذراً، حدث خطأ تقني. ممكن تعيد الجواب؟",
                "current_stage": interview_state["current_stage"]
            }

    def _build_agent_system_prompt(
        self,
        candidate_name: str,
        target_role: str,
        candidate_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build intelligent agent system prompt with role-specific logic."""

        role_requirements = {
            "baker": {
                "key_skills": ["صناعة الخبز", "تحضير العجين", "العمل الصباحي"],
                "dealbreakers": [
                    "لا يستطيع العمل الساعة 4 صباحاً",
                    "لا خبرة في المطابخ",
                ],
                "critical_questions": [
                    "ما خبرتك في المخابز أو المطابخ؟",
                    "كيف تتصرف لو تعطل الفرن أثناء العمل؟",
                    "هل مستعد للعمل من الساعة 4 صباحاً؟",
                ],
            },
            "cashier": {
                "key_skills": ["خدمة العملاء", "التعامل مع المال", "الصبر"],
                "dealbreakers": [
                    "سوء التواصل",
                    "لا يستطيع التعامل مع الزبائن",
                ],
                "critical_questions": [
                    "شو خبرتك في خدمة العملاء؟",
                    "كيف تتعامل مع زبون منزعج أو غاضب؟",
                    "هل مرتاح تستخدم الكاشير والمال؟",
                ],
            },
            "delivery_driver": {
                "key_skills": ["رخصة قيادة سارية", "معرفة الطرق", "اللياقة البدنية"],
                "dealbreakers": ["لا يملك رخصة قيادة", "سجل قيادة سيء"],
                "critical_questions": [
                    "هل معك رخصة قيادة سارية؟",
                    "شو تسوي لو تأخرت في التوصيل بسبب الزحمة؟",
                    "تقدر تشيل أوزان لحد 30 كيلو؟",
                ],
            },
        }

        requirements = role_requirements.get(
            target_role, role_requirements["baker"]
        )

        context_info = ""
        if candidate_context:
            context_info = f"""
معلومات المتقدم:
- الاسم: {candidate_name}
- الوظيفة المطلوبة: {target_role.replace('_', ' ')}
- رقم الهاتف: {candidate_context.get('phone_number', 'غير متوفر')}
"""

        return f"""# هويتك
أنت سارة، مسؤولة توظيف ذكية في مخبز Golden Crust. أنت لست روبوت يقرأ سكريبت - أنت وكيل ذكي يفكر ويحلل ويتخذ قرارات.

{context_info}

# طبقة الدفء والتعاطف (إلزامية)
قبل كل سؤال، استخدمي عبارة تشجيعية قصيرة من هذه القائمة:
- يا سلام
- جميل جداً
- فهمت عليك
- الله يوفقك
- ممتاز
- حلو
- تمام

مثال: "يا سلام! شو نوع الخبز كنت تسويه؟" أو "جميل جداً! كم سنة خبرة؟"

# متطلبات الوظيفة ({target_role})
المهارات المطلوبة: {', '.join(requirements['key_skills'])}
العوامل الحاسمة: {', '.join(requirements['dealbreakers'])}

الأسئلة الأساسية:
{chr(10).join([f"- {q}" for q in requirements['critical_questions']])}

# قدراتك الذكية

## 1. التفكير السياقي
- احلّلي كل إجابة يعطيها المتقدم
- إذا ذكر معلومة مهمة → اسألي عنها بالتفصيل
- إذا ذكر شيء غامض → اطلبي توضيح
- إذا أجاب على سؤال جزئياً → اسألي الجزء المتبقي

## 2. الأسئلة المتابعة الذكية
**إذا قال "اشتغلت في مخبز":** → "يا سلام! كم سنة؟" أو "جميل! شو كان دورك؟"
**إذا قال "5 سنين خبرة":** → "ممتاز! شو نوع الخبز اللي كنت تسويه؟"
**إذا قال "ما عندي خبرة":** → "فهمت عليك! ليش مهتم بالوظيفة هذي؟"
**إذا قال "اشتغلت كاشير":** → "حلو! كيف كنت تتعامل مع الزبائن الصعبين؟"

## 3. تتبع التقدم
- احفظي أي أسئلة طرحتيها (لا تكرري)
- مستوى خبرة المتقدم (مبتدئ / متوسط / خبير)
- إذا وصلتي لـ 3-4 تبادلات → اختمي المقابلة

## 4. اتخاذ القرارات
- إذا المتقدم خبير → اسألي أسئلة متقدمة
- إذا مبتدئ → اسألي أسئلة بسيطة
- إذا فيه dealbreaker → اختمي المقابلة بلطف

# قواعد صارمة

## القاعدة 1: طول الرد (20 كلمة أو أقل حرفياً)
كل رد منك أقل من 20 كلمة عربية. ممنوع الجمل الطويلة.

## القاعدة 2: سؤال واحد فقط
اسألي سؤال واحد في كل رد. لا تقولي "وكمان" أو "أيضاً".

## القاعدة 3: اللغة العربية
كل ردودك بالعربية الطبيعية. استخدمي "شو" و "هيك" و "مرتاح".

## القاعدة 4: الاعتراف ثم السؤال
1. عبارة دفء (يا سلام / جميل / ممتاز) — 2-4 كلمات
2. سؤال متابعة واحد
3. توقف

مثال صحيح: "يا سلام! 5 سنين خبرة قوية. شو نوع الخبز كنت تسويه؟"
مثال خاطئ: "ممتاز! الآن بدي أسألك عن أنواع الخبز وكمان كيف تتعامل مع ضغط العمل؟"

## القاعدة 5: لا تكرار
إذا المتقدم أجاب، لا تسأليه مرة ثانية.

# مراحل المقابلة

## المرحلة 1: الترحيب (أول رسالة فقط)
"مرحباً {candidate_name}! أنا سارة من مخبز Golden Crust. جاهز نبدأ؟"

## المرحلة 2: تقييم الخبرة
اسألي عن خبرته في {target_role}. اسألي سؤال متابعة حسب ما قال.

## المرحلة 3: السؤال الموقفي
بناءً على مستوى خبرته، اطرحي سيناريو واقعي.

## المرحلة 4: المتطلبات العملية
تأكدي من المتطلبات الحاسمة (رخصة، دوام صباحي).

## المرحلة 5: الاختتام
"تمام! شكراً على وقتك يا {candidate_name}. راح نتواصل معك خلال 48 ساعة."

أنت وكيل ذكي، لست مسجل صوتي."""

    def _format_messages_for_gpt(
        self,
        system_prompt: str,
        conversation_history: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        """Format conversation history for Groq Models."""

        messages = [{"role": "system", "content": system_prompt}]

        for turn in conversation_history:
            role = turn.get("role", "user")
            content = turn.get("content") or turn.get("message", "")

            if role == "assistant":
                messages.append({"role": "assistant", "content": content})
            else:
                messages.append({"role": "user", "content": content})

        return messages

    def _update_interview_state(
        self,
        candidate_id: str,
        conversation_history: List[Dict[str, str]],
    ) -> None:
        """Track interview progress for this candidate."""

        self.interview_states[candidate_id] = {
            "turn_count": len(conversation_history),
            "last_updated": datetime.now().isoformat(),
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

    def generate_final_evaluation(
        self,
        conversation_history: List[Dict[str, str]],
        target_role: str,
    ) -> Dict[str, Any]:
        """
        Generate comprehensive evaluation after interview ends using Groq.
        """

        conversation_text = "\n".join(
            [
                f"{turn.get('role', 'user')}: {turn.get('content') or turn.get('message', '')}"
                for turn in conversation_history
            ]
        )

        evaluation_prompt = f"""أنت خبير تقييم موارد بشرية. قيّم هذه المقابلة:

الوظيفة: {target_role}

المحادثة:
{conversation_text}

قدّم تقييم شامل يتضمن:
1. النتيجة الإجمالية (0-100)
2. نقاط القوة (bullet points)
3. نقاط الضعف (bullet points)
4. التوصية: strong_hire أو maybe أو reject
5. خلاصة سطر واحد

أعطِ الرد كـ JSON بهذا الشكل فقط وبدون أي نصوص إضافية:
{{
  "overall_score": 85,
  "strengths": ["خبرة 5 سنوات", "تواصل جيد"],
  "weaknesses": ["لا يستطيع العمل صباحاً"],
  "recommendation": "maybe",
  "bottom_line": "مرشح جيد لكن لديه قيد على الدوام الصباحي"
}}"""

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "أنت خبير تقييم. أعطِ ردود JSON فقط.",
                    },
                    {"role": "user", "content": evaluation_prompt},
                ],
                max_tokens=500,
                temperature=0.3,
                # Groq يدعم وضع JSON لضمان دقة المخرجات
                response_format={"type": "json_object"}
            )

            evaluation_text = response.choices[0].message.content or ""
            evaluation_text = evaluation_text.strip()

            return json.loads(evaluation_text)

        except Exception as e:
            print(f"❌ Error generating evaluation via Groq: {str(e)}")
            return {
                "overall_score": 50,
                "strengths": ["تعذر التقييم"],
                "weaknesses": ["خطأ تقني"],
                "recommendation": "needs_review",
                "bottom_line": "تعذر التقييم - يحتاج مراجعة يدوية",
            }
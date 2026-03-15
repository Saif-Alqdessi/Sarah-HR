"""
Credibility Scorer - Form vs Interview Comparison
Assesses candidate credibility by comparing registration form data
with the interview transcript. Uses MultiProviderLLM (Groq-first) so
the scorer never touches OpenAI directly and never crashes the interview.
"""

import asyncio
import concurrent.futures
import json
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class CredibilityScorer:
    """
    Compares registration form answers with interview transcript
    to assess candidate credibility.
    Uses Groq (via MultiProviderLLM) so OpenAI quota errors never crash the scorer.
    """

    def __init__(self):
        # Lazy-loaded — avoids import-time side-effects
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            from app.core.llm_manager import MultiProviderLLM
            self._llm = MultiProviderLLM()
        return self._llm

    def score_credibility(
        self,
        registration_form: Dict[str, Any],
        transcript: List[Dict[str, str]],
        detected_inconsistencies: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive credibility assessment
        
        Args:
            registration_form: Pre-interview form data
            transcript: Interview conversation history
            detected_inconsistencies: Real-time detected flags
        
        Returns:
            {
                "credibility_score": 85,
                "credibility_level": "عالية",
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

أعطِ رد JSON فقط بدون أي نص إضافي:

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
  "recommendation": "يحتاج تحقق إضافي",
  "bottom_line_summary": "ملخص من جملة واحدة عن مصداقية المتقدم"
}}

معايير الدرجة:
- 90-100: مصداقية عالية جداً (موثوق بشكل كامل)
- 75-89: مصداقية عالية (موثوق)
- 60-74: مصداقية متوسطة (مقبول مع متابعة)
- 40-59: مصداقية منخفضة (يحتاج تحقق إضافي)
- 0-39: مصداقية منخفضة جداً (غير موثوق)

التوصيات:
- "موثوق بشكل كامل" → 90-100
- "موثوق" → 75-89
- "مقبول مع متابعة" → 60-74
- "يحتاج تحقق إضافي" → 40-59
- "غير موثوق" → 0-39"""

        try:
            # Run the async generate() inside a fresh event loop in a worker thread,
            # so this sync method works correctly inside both sync and async contexts.
            messages = [
                {
                    "role": "system",
                    "content": "أنت خبير تقييم مصداقية موارد بشرية. أعطِ JSON فقط بدون أي نص إضافي.",
                },
                {
                    "role": "user",
                    "content": scoring_prompt,
                },
            ]
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    self.llm.generate(messages, temperature=0.2, max_tokens=1200),
                )
                response_text = future.result(timeout=45)

            # Strip markdown code fences if the model wrapped the JSON
            response_text = response_text.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            credibility_data = json.loads(response_text)

            # Ensure all required fields exist
            credibility_data.setdefault("credibility_score", 50)
            credibility_data.setdefault("credibility_level", "متوسطة")
            credibility_data.setdefault("inconsistencies_found", [])
            credibility_data.setdefault("consistency_areas", [])
            credibility_data.setdefault("red_flags", [])
            credibility_data.setdefault("recommendation", "يحتاج مراجعة")
            credibility_data.setdefault("bottom_line_summary", "تقييم مصداقية قياسي")

            return credibility_data

        except json.JSONDecodeError as e:
            logger.error("JSON parsing error in credibility scoring: %s", e)
            return self._get_default_credibility_score()
        except Exception as e:
            # Log the error but NEVER let it crash the interview
            logger.error(
                "Credibility scoring error (provider=%s): %s — returning safe default",
                getattr(self._llm, 'providers', [('unknown',)])[0][0] if self._llm else 'none',
                e,
            )
            return self._get_default_credibility_score()

    
    def _format_form_data(self, form: Dict[str, Any]) -> str:
        """
        Format registration form data for display in prompt
        """
        if not form:
            return "لا توجد بيانات من الطلب الإلكتروني"
        
        lines = []
        
        # Group fields for better organization
        important_fields = {
            "years_of_experience": "عدد سنوات الخبرة",
            "has_field_experience": "خبرة في نفس المجال",
            "expected_salary": "الراتب المتوقع",
            "can_start_immediately": "إمكانية البدء فوراً",
            "proximity_to_branch": "قرب السكن من الفرع",
            "academic_status": "المسار الأكاديمي",
            "prayer_regularity": "المواظبة على الصلاة",
            "is_smoker": "التدخين",
            "target_role": "المسمى الوظيفي المطلوب",
            "nationality": "الجنسية",
            "age_range": "الفئة العمرية"
        }
        
        for key, label in important_fields.items():
            value = form.get(key)
            if value:
                lines.append(f"- {label}: {value}")
        
        # Add any other fields not in the important list
        for key, value in form.items():
            if value and key not in important_fields and not key.startswith('_'):
                lines.append(f"- {key}: {value}")
        
        return "\n".join(lines) if lines else "لا توجد بيانات متاحة"
    
    def _format_transcript(self, transcript: List[Dict[str, str]]) -> str:
        """
        Format interview transcript for analysis
        """
        if not transcript:
            return "لا يوجد نص مقابلة"
        
        lines = []
        for turn in transcript:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            
            if not content:
                continue
            
            speaker = "سارة (المحاورة)" if role == "assistant" else "المتقدم"
            lines.append(f"{speaker}: {content}")
        
        return "\n".join(lines) if lines else "لا يوجد محتوى"
    
    def _get_default_credibility_score(self) -> Dict[str, Any]:
        """
        Return default score structure on error
        """
        return {
            "credibility_score": 50,
            "credibility_level": "غير محدد",
            "inconsistencies_found": [],
            "consistency_areas": [],
            "red_flags": ["فشل التقييم التلقائي - يحتاج مراجعة يدوية"],
            "recommendation": "يحتاج مراجعة يدوية",
            "bottom_line_summary": "لم يتم التقييم بسبب خطأ تقني"
        }
    
    def get_credibility_level_from_score(self, score: int) -> str:
        """
        Convert numeric score to Arabic level label
        
        Args:
            score: Credibility score (0-100)
        
        Returns:
            Arabic credibility level
        """
        if score >= 90:
            return "عالية جداً"
        elif score >= 75:
            return "عالية"
        elif score >= 60:
            return "متوسطة"
        elif score >= 40:
            return "منخفضة"
        else:
            return "منخفضة جداً"
    
    def get_recommendation_from_score(self, score: int) -> str:
        """
        Convert numeric score to hiring recommendation
        
        Args:
            score: Credibility score (0-100)
        
        Returns:
            Arabic recommendation
        """
        if score >= 90:
            return "موثوق بشكل كامل"
        elif score >= 75:
            return "موثوق"
        elif score >= 60:
            return "مقبول مع متابعة"
        elif score >= 40:
            return "يحتاج تحقق إضافي"
        else:
            return "غير موثوق"
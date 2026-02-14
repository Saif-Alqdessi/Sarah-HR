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

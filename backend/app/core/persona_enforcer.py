"""
Persona Enforcement Layer
Ensures strict Jordanian Arabic dialect and zero English tolerance
"""

import re
from typing import Tuple
from langdetect import detect, LangDetectException


class PersonaEnforcer:
    """
    Enforces Sarah's persona: Jordanian Arabic only, no English, natural dialect
    """
    
    # English detection patterns
    ENGLISH_PATTERNS = [
        r'\b(the|and|is|are|was|were|have|has|had)\b',
        r'\b(this|that|these|those|what|when|where|why|how)\b',
        r'\b(experience|salary|job|work|candidate|interview)\b',
        r'\b(years?|months?|days?|time|because|actually)\b',
        r'\b[a-zA-Z]{4,}\b'  # Words with 4+ English letters
    ]
    
    # MSA → Jordanian conversions
    MSA_TO_JORDANIAN = {
        'ماذا': 'شو',
        'لماذا': 'ليش',
        'أين': 'وين',
        'كيف حالك': 'كيفك',
        'متى': 'إيمتى',
        'هل': 'هل',  # Can stay but optional
        'سوف': 'راح',
        'سأقوم': 'راح',
        'أريد': 'بدي',
        'أنت': 'انت',
        'لديك': 'عندك',
        'هل لديك': 'عندك',
        'ذلك': 'هاد',
        'هذا': 'هاد',
        'جيد': 'منيح',
        'ممتاز': 'كتير منيح'
    }
    
    # Jordanian markers (should be present)
    JORDANIAN_MARKERS = [
        'شو', 'ليش', 'وين', 'كيفك', 'راح', 'عم', 'بدي',
        'هيك', 'منيح', 'كتير', 'شوي', 'هسا', 'بعدين',
        'يعني', 'انت', 'عندك', 'حكيلي', 'شفت', 'انك'
    ]
    
    def __init__(self):
        self.violation_count = 0
    
    def enforce(self, text: str, strict_mode: bool = True) -> Tuple[bool, str, str]:
        """
        Enforce persona rules on text
        
        Args:
            text: LLM generated text to check
            strict_mode: If True, reject on any violation; If False, auto-correct
            
        Returns:
            (is_valid, error_message, corrected_text)
        """
        
        # Step 1: Check for English
        has_english, english_error = self._detect_english(text)
        if has_english:
            if strict_mode:
                self.violation_count += 1
                return False, english_error, text
            else:
                # In non-strict mode, we'd attempt translation (not implemented)
                pass
        
        # Step 2: Convert MSA to Jordanian
        text = self._convert_to_jordanian(text)
        
        # Step 3: Validate Jordanian markers
        has_jordanian = self._has_jordanian_markers(text)
        if not has_jordanian:
            warning = "⚠️ Weak Jordanian dialect - consider regenerating"
            print(warning)
        
        return True, "", text
    
    def _detect_english(self, text: str) -> Tuple[bool, str]:
        """
        Detect English words in text
        
        Returns:
            (has_english, error_message)
        """
        # Check patterns
        for pattern in self.ENGLISH_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                return True, f"English detected: {matches}"
        
        # Fallback: langdetect
        try:
            # Remove Arabic text and check what's left
            text_no_arabic = re.sub(r'[\u0600-\u06FF\s]+', '', text)
            if len(text_no_arabic) > 10:
                lang = detect(text_no_arabic)
                if lang == 'en':
                    return True, f"English detected via langdetect"
        except LangDetectException:
            pass
        
        return False, ""
    
    def _convert_to_jordanian(self, text: str) -> str:
        """
        Replace MSA phrases with Jordanian equivalents
        """
        for msa, jordanian in self.MSA_TO_JORDANIAN.items():
            text = text.replace(msa, jordanian)
        return text
    
    def _has_jordanian_markers(self, text: str) -> bool:
        """
        Check if text contains Jordanian-specific markers
        """
        found_markers = [marker for marker in self.JORDANIAN_MARKERS if marker in text]
        return len(found_markers) >= 1
    
    def get_stats(self) -> dict:
        """Return enforcement statistics"""
        return {
            "total_violations": self.violation_count
        }

    def enforce_facts(self, text: str, contract_exp: int = None, contract_salary: int = None) -> Tuple[bool, str]:
        """
        Hard guard against LLM hallucinating years of experience or salary.
        Stops the AI from mixing up 5 years and 10 years, catching text formats (خمس).
        """
        is_valid = True
        corrected = text
        
        # Arabic number mapping
        arabic_numbers = {
            'واحد': 1, 'واحدة': 1, 'سنتين': 2, 'تنين': 2, 'اثنين': 2,
            'تلات': 3, 'ثلاث': 3, 'تلاتة': 3, 'ثلاثة': 3,
            'اربع': 4, 'أربع': 4, 'اربعة': 4, 'أربعة': 4,
            'خمس': 5, 'خمسة': 5, 'خمست': 5,
            'ست': 6, 'ستة': 6,
            'سبع': 7, 'سبعة': 7,
            'تمن': 8, 'ثمن': 8, 'تمانية': 8, 'ثمانية': 8,
            'تسع': 9, 'تسعة': 9,
            'عشر': 10, 'عشرة': 10
        }
        
        if contract_exp is not None:
            # 1. Match digits (5 سنين)
            exp_pattern = r'(\d+)\s*(سنة|سنوات|سنين|year|years)'
            for num_str, unit in re.findall(exp_pattern, text):
                num = int(num_str)
                if 0 < num <= 50 and num != contract_exp:
                    corrected = corrected.replace(f"{num_str} {unit}", f"{contract_exp} {unit}")
                    is_valid = False
            
            # 2. Match word numbers (خمس سنين)
            word_exp_pattern = r'\b(واحد|واحدة|سنتين|تنين|اثنين|تلات|ثلاث|تلاتة|ثلاثة|اربع|أربع|اربعة|أربعة|خمس|خمسة|خمست|ست|ستة|سبع|سبعة|تمن|ثمن|تمانية|ثمانية|تسع|تسعة|عشر|عشرة)\s*(سنة|سنوات|سنين|year|years)\b'
            for word, unit in re.findall(word_exp_pattern, text):
                num = arabic_numbers.get(word)
                if num and num != contract_exp:
                    corrected = corrected.replace(f"{word} {unit}", f"{contract_exp} {unit}")
                    is_valid = False
            
        if contract_salary is not None:
            sal_pattern = r'(\d+)\s*(دينار|JOD|ليرة)'
            for amount_str, currency in re.findall(sal_pattern, text):
                amount = int(amount_str)
                if abs(amount - contract_salary) > contract_salary * 0.5:
                    corrected = corrected.replace(f"{amount_str} {currency}", f"{contract_salary} {currency}")
                    is_valid = False
        
        return is_valid, corrected


class CandidateLanguageMonitor:
    """
    Monitors candidate's language and gently redirects if they use English
    """
    
    def check_candidate_input(self, user_input: str) -> Tuple[bool, str]:
        """
        Check if candidate used English
        
        Returns:
            (used_english, gentle_redirect_message)
        """
        # Simple English detection
        english_words = re.findall(r'\b[a-zA-Z]{3,}\b', user_input)
        
        if len(english_words) >= 2:
            redirect = "خلينا نحكي عربي أحسن 😊"
            return True, redirect
        
        return False, ""

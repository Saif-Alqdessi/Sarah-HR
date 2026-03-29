"""
Enhanced lexical filtering with pattern detection
Catches noise that simple word counts miss

6-Layer Validation Pipeline:
  1. Basic Cleaning (punctuation strip)
  2. Filler Word Removal (Arabic + English)
  3. Repetitive Pattern Detection
  4. Single Syllable Dominance Detection
  5. Unique Word Count
  6. Lexical Diversity Score
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

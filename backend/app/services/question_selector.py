# =============================================================================
# DATABASE QUESTION SELECTOR SERVICE
# backend/app/services/question_selector.py
# =============================================================================

from typing import List, Dict, Optional
import random
import logging
import time
from supabase import Client

logger = logging.getLogger(__name__)

# Hardcoded total — the question_bank MUST have exactly 6 categories.
# This prevents DB failures from causing premature interview termination.
TOTAL_CATEGORIES = 6


class DatabaseQuestionSelector:
    """
    Fetches questions from database question_bank table.
    Replaces hardcoded question lists.
    """

    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self._category_cache = None

    def get_total_categories(self) -> int:
        """Always returns 6. This is the canonical source of truth."""
        return TOTAL_CATEGORIES

    def get_all_categories(self) -> List[Dict]:
        """Fetch all interview categories with metadata (cached)."""
        if self._category_cache:
            return self._category_cache

        try:
            result = self.supabase.table("question_bank")\
                .select("category_id, category_name_ar, category_name_en, category_stage")\
                .eq("is_active", True)\
                .execute()

            if result.data:
                # Group by category_id
                categories_dict = {}
                for row in result.data:
                    cat_id = row['category_id']
                    if cat_id not in categories_dict:
                        categories_dict[cat_id] = {
                            'category_id': cat_id,
                            'category_name_ar': row['category_name_ar'],
                            'category_name_en': row['category_name_en'],
                            'category_stage': row['category_stage']
                        }

                # Sort by category_id
                self._category_cache = sorted(categories_dict.values(), key=lambda x: x['category_id'])
                return self._category_cache

            logger.warning("question_bank returned no categories")
            return []
        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            return []

    def get_category_by_index(self, category_index: int) -> Optional[Dict]:
        """Get category by index (0-based)."""
        categories = self.get_all_categories()
        if 0 <= category_index < len(categories):
            return categories[category_index]
        return None

    def select_random_question(
        self,
        category_id: int,
        exclude_ids: List[str] = None,
        max_retries: int = 3,
    ) -> Optional[Dict]:
        """
        Select random question from category with retry logic.

        Args:
            category_id: Category ID (1-6)
            exclude_ids: List of question IDs already asked
            max_retries: Number of times to retry on failure

        Returns:
            Question dict or None (only after all retries exhausted)
        """
        exclude_ids = exclude_ids or []

        for attempt in range(1, max_retries + 1):
            try:
                # Fetch all questions for this category
                result = self.supabase.table("question_bank")\
                    .select("*")\
                    .eq("category_id", category_id)\
                    .eq("is_active", True)\
                    .order("display_order")\
                    .execute()

                if not result.data:
                    logger.warning(
                        "No questions found for category %d (attempt %d/%d)",
                        category_id, attempt, max_retries,
                    )
                    if attempt < max_retries:
                        time.sleep(0.5)
                        continue
                    return None

                # Filter excluded
                available = [q for q in result.data if q['question_id'] not in exclude_ids]

                if not available:
                    logger.info("All questions used in category %d, resetting pool", category_id)
                    available = result.data

                # Random selection
                selected = random.choice(available)

                logger.info("Selected Q%s from category %d (attempt %d)", selected['question_id'], category_id, attempt)

                return {
                    "question_id": selected["question_id"],
                    "question_text_ar": selected["question_text_ar"],
                    "question_text_en": selected.get("question_text_en"),
                    "category_id": selected["category_id"],
                    "category_name_ar": selected["category_name_ar"],
                    "category_name_en": selected["category_name_en"],
                    "category_stage": selected["category_stage"],
                    "weight": selected["weight"]
                }
            except Exception as e:
                logger.error(
                    "Error selecting question for category %d (attempt %d/%d): %s",
                    category_id, attempt, max_retries, e,
                )
                if attempt < max_retries:
                    time.sleep(0.5)

        logger.error("All %d retries failed for category %d", max_retries, category_id)
        return None

    def get_category_name(self, category_index: int) -> str:
        """Get Arabic category name by index."""
        category = self.get_category_by_index(category_index)
        return category["category_name_ar"] if category else "Unknown"

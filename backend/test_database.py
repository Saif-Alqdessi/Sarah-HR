"""Test database connection and question fetching"""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.supabase_client import get_supabase_client
from app.services.question_selector import DatabaseQuestionSelector

def main():
    print("=" * 60)
    print("  DATABASE CONNECTION TEST")
    print("=" * 60)

    # Test Supabase connection
    try:
        supabase = get_supabase_client()
        print("[OK]  Supabase connected")
    except Exception as e:
        print(f"[FAIL] Supabase connection failed: {e}")
        return

    # Test question selector
    try:
        selector = DatabaseQuestionSelector(supabase)
        print("[OK]  Question selector initialized")
    except Exception as e:
        print(f"[FAIL] Question selector failed: {e}")
        return

    # Get all categories
    print("\n" + "=" * 60)
    print("  CATEGORIES IN DATABASE")
    print("=" * 60)

    categories = selector.get_all_categories()
    print(f"Total categories: {len(categories)}")

    for cat in categories:
        print(f"\n  {cat['category_id']}. {cat['category_name_ar']}")
        print(f"     English: {cat['category_name_en']}")
        print(f"     Stage: {cat['category_stage']}")

    # Test random question selection
    print("\n" + "=" * 60)
    print("  RANDOM QUESTION SELECTION")
    print("=" * 60)

    for category_id in range(1, 7):
        question = selector.select_random_question(category_id=category_id)
        if question:
            q_text = question['question_text_ar']
            display = q_text[:60] + "..." if len(q_text) > 60 else q_text
            print(f"\nCategory {category_id}: {question['category_name_ar']}")
            print(f"  ID: {question['question_id']}")
            print(f"  Q: {display}")
        else:
            print(f"\n[WARN] No question found for category {category_id}")

    # Test candidate fetch with Arabic values
    print("\n" + "=" * 60)
    print("  CANDIDATE FETCH (Arabic Values)")
    print("=" * 60)

    try:
        result = supabase.table("candidates")\
            .select("*")\
            .eq("id", "aaaaaaaa-bbbb-cccc-dddd-111111111111")\
            .execute()

        if result.data:
            candidate = result.data[0]
            print(f"[OK]  Candidate: {candidate['full_name']}")
            print(f"      Role: {candidate['target_role']}")
            print(f"      Experience: {candidate['years_of_experience']} years")
            print(f"      Has field exp: '{candidate.get('has_field_experience', 'N/A')}' (Arabic)")
            print(f"      Smoker: '{candidate.get('is_smoker', 'N/A')}' (Arabic)")

            # Validate Arabic values
            field_exp = candidate.get('has_field_experience')
            smoker = candidate.get('is_smoker')

            if field_exp and field_exp in ['نعم', 'لا']:
                print(f"[OK]  has_field_experience is Arabic: '{field_exp}'")
            elif field_exp:
                print(f"[WARN] has_field_experience is NOT Arabic: '{field_exp}'")

            if smoker and smoker in ['نعم', 'لا']:
                print(f"[OK]  is_smoker is Arabic: '{smoker}'")
            elif smoker:
                print(f"[WARN] is_smoker is NOT Arabic: '{smoker}'")
        else:
            print("[WARN] Test candidate aaaaaaaa-bbbb-cccc-dddd-111111111111 not found")
    except Exception as e:
        print(f"[FAIL] Candidate fetch failed: {e}")

    print("\n" + "=" * 60)
    print("  ALL DATABASE TESTS COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    main()

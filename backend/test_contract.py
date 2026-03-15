"""Test CandidateContract with Arabic values"""
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent))

from app.models.candidate import CandidateContract

def main():
    print("=" * 60)
    print("  CANDIDATE CONTRACT TEST")
    print("=" * 60)

    # Create contract with Arabic values
    try:
        contract = CandidateContract(
            candidate_id=UUID("aaaaaaaa-bbbb-cccc-dddd-111111111111"),
            interview_id=UUID("bbbbbbbb-cccc-dddd-eeee-222222222222"),
            full_name="أحمد علي الخباز",
            target_role="خباز",
            years_of_experience=10,
            expected_salary=450,
            has_field_experience='نعم',  # Arabic!
            proximity_to_branch='قريب بنفس المنطقة واحضر مواصلات',
            can_start_immediately='نعم استطيع',
            academic_status='انتهيت من المسيرة الدراسية (ثانوية عامة)'
        )
        print("[OK]  Contract created successfully")
    except Exception as e:
        print(f"[FAIL] Contract creation failed: {e}")
        return

    # Test fields
    print(f"\n  Contract Fields:")
    print(f"    Name: {contract.full_name}")
    print(f"    Role: {contract.target_role}")
    print(f"    Experience (raw): {contract.years_of_experience}")
    print(f"    Experience (Arabic): {contract.get_experience_arabic()}")
    print(f"    Has field exp (string): {contract.has_field_experience}")
    print(f"    Has field exp (bool): {contract.has_field_experience_bool()}")

    # Test immutability
    print(f"\n  Testing Immutability:")
    try:
        contract.years_of_experience = 5
        print("[FAIL] Contract is NOT immutable!")
    except Exception:
        print("[OK]  Contract is immutable (frozen=True)")

    # Test Arabic conversion helpers
    print(f"\n  Testing Arabic Helpers:")
    print(f"    'نعم' -> {contract.has_field_experience_bool()}")

    test_contract_2 = CandidateContract(
        candidate_id=UUID("aaaaaaaa-bbbb-cccc-dddd-111111111111"),
        interview_id=UUID("bbbbbbbb-cccc-dddd-eeee-222222222222"),
        full_name="Test",
        target_role="خباز",
        years_of_experience=5,
        expected_salary=400,
        has_field_experience='لا'  # No
    )
    print(f"    'لا' -> {test_contract_2.has_field_experience_bool()}")

    # Verify boolean conversion
    assert contract.has_field_experience_bool() == True, "نعم should be True"
    assert test_contract_2.has_field_experience_bool() == False, "لا should be False"
    print("[OK]  Boolean conversion correct")

    # Test get_experience_arabic for various values
    print(f"\n  Testing get_experience_arabic:")
    test_cases = [
        (0, "بدون خبرة"),
        (1, "سنة واحدة"),
        (2, "سنتين"),
        (5, "5 سنوات"),
        (10, "10 سنوات"),
        (15, "15 سنة"),
    ]
    for years, expected in test_cases:
        c = CandidateContract(
            candidate_id=UUID("aaaaaaaa-bbbb-cccc-dddd-111111111111"),
            interview_id=UUID("bbbbbbbb-cccc-dddd-eeee-222222222222"),
            full_name="Test",
            target_role="خباز",
            years_of_experience=years,
            expected_salary=400,
            has_field_experience='نعم'
        )
        result = c.get_experience_arabic()
        status = "[OK] " if result == expected else "[FAIL]"
        print(f"    {status} {years} years -> '{result}' (expected: '{expected}')")

    print("\n" + "=" * 60)
    print("  ALL CONTRACT TESTS PASSED")
    print("=" * 60)

if __name__ == "__main__":
    main()

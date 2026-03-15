"""
test_sarah.py — Phase 4 Grand Health Check
Run from the backend/ directory: python test_sarah.py

Tests:
  [1] Groq LLM via MultiProviderLLM
  [2] Local Fact Verification (regex, zero LLM calls)
  [3] Supabase Write Permission (service_role key)
"""

import sys
import os
import asyncio
import uuid

# Make sure 'app' package is importable when running from backend/
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ── colour helpers ────────────────────────────────────────────────────────── #
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}[OK]{RESET}  {msg}")
def fail(msg): print(f"  {RED}[FAIL]{RESET} {msg}")
def warn(msg): print(f"  {YELLOW}[WARN]{RESET} {msg}")


# ═══════════════════════════════════════════════════════════════════════════ #
# TEST 1: Groq LLM via MultiProviderLLM                                      #
# ═══════════════════════════════════════════════════════════════════════════ #

async def test_groq():
    print("\n" + "="*58)
    print("  TEST 1: Groq LLM (MultiProviderLLM)")
    print("="*58)

    try:
        from app.core.llm_manager import MultiProviderLLM
        llm = MultiProviderLLM()
        ok("MultiProviderLLM initialised")

        messages = [
            {"role": "system", "content": "أنت سارة، مسؤولة توظيف في مخبز. رد بجملة واحدة باللهجة الأردنية."},
            {"role": "user",   "content": "مرحباً"},
        ]
        response = await llm.generate(messages, temperature=0.2, max_tokens=60)

        if response and len(response) > 2:
            ok(f"Groq response received: \"{response[:80]}\"")
        else:
            fail(f"Empty or too-short response: {repr(response)}")
            return False

        status = llm.get_status()
        ok(f"Provider status: {status}")
        return True

    except Exception as e:
        fail(f"MultiProviderLLM error: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════ #
# TEST 2: Local Fact Verification                                             #
# ═══════════════════════════════════════════════════════════════════════════ #

def test_local_fact_verification():
    print("\n" + "="*58)
    print("  TEST 2: Local Fact Verification (zero LLM calls)")
    print("="*58)

    try:
        from app.core.interview_agent import InterviewAgent
        from app.models.candidate import CandidateContract

        agent = InterviewAgent()
        ok("InterviewAgent initialised")

        # Build a minimal frozen contract (Ahmad Developer)
        contract = CandidateContract(
            candidate_id="test-candidate-001",
            interview_id="test-interview-001",
            full_name="Ahmad Developer",
            target_role="cashier",
            years_of_experience=3,
            expected_salary=800,
            has_field_experience=True,
            proximity_to_branch="قريب - أقل من 5 كم",
        )
        ok(f"Contract created | exp={contract.years_of_experience} yrs | salary={contract.expected_salary} JOD | hash={contract.contract_hash}")

        # 2a: response with CORRECT facts (should pass untouched)
        correct_resp = "أهلاً! شفت بطلبك إنك عندك 3 سنوات خبرة، هيك صح؟"
        is_valid, corrected = agent._verify_facts_locally(correct_resp, contract)
        if is_valid and corrected == correct_resp:
            ok("Correct facts pass verification unchanged")
        else:
            fail(f"Correct facts wrongly flagged: {corrected}")
            return False

        # 2b: response with WRONG experience (should be auto-corrected)
        wrong_resp = "أهلاً! شفت بطلبك إنك عندك 7 سنوات خبرة، هيك صح؟"
        is_valid, corrected = agent._verify_facts_locally(wrong_resp, contract)
        if not is_valid and "3 سنوات" in corrected:
            ok(f"Hallucination auto-corrected: '7 سنوات' -> '3 سنوات'")
        else:
            fail(f"Hallucination NOT caught. is_valid={is_valid}, corrected='{corrected}'")
            return False

        # 2c: response with WRONG salary (should be auto-corrected)
        wrong_salary = "راتبك المتوقع 200 دينار، صح؟"
        is_valid, corrected = agent._verify_facts_locally(wrong_salary, contract)
        if not is_valid and "800 دينار" in corrected:
            ok(f"Salary hallucination auto-corrected: '200' -> '800'")
        else:
            fail(f"Salary NOT caught. is_valid={is_valid}, corrected='{corrected}'")
            return False

        return True

    except Exception as e:
        fail(f"Local fact verification error: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════ #
# TEST 3: Supabase Write Permission                                           #
# ═══════════════════════════════════════════════════════════════════════════ #

def test_supabase_write():
    print("\n" + "="*58)
    print("  TEST 3: Supabase Write Permission")
    print("="*58)

    try:
        from app.db.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        ok("Supabase client created")

        # Decode the key type from env to warn early
        key_in_use = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY", "")
        if '"role":"anon"' in key_in_use or (key_in_use and "anon" in _decode_jwt_role(key_in_use)):
            warn("SUPABASE_SERVICE_ROLE_KEY appears to be an anon key — INSERT will likely fail (RLS).")
            warn("Fix: Dashboard -> Settings -> API -> copy the service_role secret key.")

        # First, find a real candidate to use as a foreign key
        candidates_resp = supabase.table("candidates").select("id").limit(1).execute()
        if not candidates_resp.data:
            warn("No candidates found in DB — skipping Supabase write test.")
            warn("Insert a candidate first, then re-run this test.")
            return None  # Not a hard fail — just warn

        candidate_id = candidates_resp.data[0]["id"]

        # Try to insert a test interview row
        test_id = str(uuid.uuid4())
        from datetime import datetime, timezone
        result = supabase.table("interviews").insert({
            "id": test_id,
            "candidate_id": candidate_id,
            "status": "in_progress",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "transcript": [],
            "detected_inconsistencies": [],
        }).execute()

        if result.data and len(result.data) > 0:
            ok(f"INSERT succeeded | interview_id={test_id[:12]}...")

            # Clean up — delete the test row
            supabase.table("interviews").delete().eq("id", test_id).execute()
            ok("Test row cleaned up")
            return True
        else:
            fail(f"INSERT returned no data. Response: {result}")
            return False

    except Exception as e:
        err_str = str(e).lower()
        if "row-level security" in err_str or "42501" in err_str or "policy" in err_str:
            fail("RLS blocked the INSERT — SUPABASE_SERVICE_ROLE_KEY is wrong (anon key used).")
            fail("Fix: Copy the real service_role key from Supabase Dashboard > Settings > API.")
        elif "foreign key" in err_str or "violates" in err_str:
            fail(f"Foreign key error: {e}")
        else:
            fail(f"Supabase error: {e}")
        return False


def _decode_jwt_role(token: str) -> str:
    """Peek at the JWT payload role without a full decode library."""
    try:
        import base64, json
        parts = token.split(".")
        if len(parts) != 3:
            return ""
        padded = parts[1] + "=="
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        return payload.get("role", "")
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════════════ #
# RUNNER                                                                     #
# ═══════════════════════════════════════════════════════════════════════════ #

async def main():
    print("\n" + "█"*58)
    print("  SARAH HEALTH CHECK — Phase 4 Grand Test")
    print("█"*58)

    results = {}

    # Run tests
    results["groq"]         = await test_groq()
    results["fact_verify"]  = test_local_fact_verification()
    results["supabase"]     = test_supabase_write()

    # Summary
    print("\n" + "="*58)
    print("  SUMMARY")
    print("="*58)

    all_pass = True
    for name, passed in results.items():
        if passed is True:
            ok(name)
        elif passed is None:
            warn(f"{name}  (skipped — see warning above)")
        else:
            fail(name)
            all_pass = False

    print()
    if all_pass:
        print(f"  {GREEN}Sarah is READY for the demo! 🚀{RESET}")
    else:
        print(f"  {RED}Some checks failed — review the output above.{RESET}")
    print()


if __name__ == "__main__":
    asyncio.run(main())

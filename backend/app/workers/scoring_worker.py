"""
Background Scoring Worker for Sarah AI
Runs independently from the WebSocket interview flow.
Polls scoring_jobs table → fetches transcript → LLM scores → saves to scores table.

Usage:
    python start_worker.py
"""

import asyncio
import logging
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Add backend to path so we can import from app.*
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.supabase_client import get_supabase_client
from app.core.llm_manager import MultiProviderLLM

logger = logging.getLogger(__name__)

# How long to wait between polls when no jobs are found
POLL_INTERVAL_SECONDS = 5

# Maximum time to wait for a single scoring job to complete
JOB_TIMEOUT_SECONDS = 120


class ScoringWorker:
    """
    Background worker that processes scoring jobs asynchronously.
    Resilient: catches all errors per-job, never crashes the loop.
    """

    def __init__(self):
        self.supabase = get_supabase_client()
        self.llm = MultiProviderLLM()
        self.is_running = False

    async def start(self):
        """Start the worker loop — runs forever until stopped."""
        self.is_running = True
        logger.info("🚀 Scoring worker started (polling every %ds)", POLL_INTERVAL_SECONDS)

        while self.is_running:
            try:
                job = self._claim_next_job()

                if job:
                    await asyncio.wait_for(
                        self._process_job(job),
                        timeout=JOB_TIMEOUT_SECONDS,
                    )
                else:
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)

            except asyncio.TimeoutError:
                logger.error("⏰ Job timed out (%ds)", JOB_TIMEOUT_SECONDS)
            except Exception as e:
                logger.error("❌ Worker loop error: %s", e, exc_info=True)
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

    def _claim_next_job(self) -> Optional[Dict]:
        """
        Atomically claim the next pending job.
        SELECT + UPDATE in one go to prevent two workers from grabbing the same job.
        """
        try:
            # Get oldest pending job
            result = (
                self.supabase.table("scoring_jobs")
                .select("*")
                .eq("status", "pending")
                .order("created_at", desc=False)
                .limit(1)
                .execute()
            )

            if not result.data:
                return None

            job = result.data[0]
            job_id = job["id"]

            # Claim it by setting status = processing
            self.supabase.table("scoring_jobs").update({
                "status": "processing",
                "started_at": datetime.utcnow().isoformat(),
            }).eq("id", job_id).eq("status", "pending").execute()

            logger.info("📋 Claimed job %s for interview %s", job_id, job.get("interview_id"))
            return job

        except Exception as e:
            logger.error("❌ Failed to claim job: %s", e)
            return None

    async def _process_job(self, job: Dict):
        """Process a single scoring job end-to-end."""
        job_id = job["id"]
        interview_id = job["interview_id"]
        candidate_id = job["candidate_id"]

        logger.info("⚙️ Processing job %s (interview: %s)", job_id, interview_id)

        try:
            # 1. Fetch interview + candidate data
            interview_data = self._fetch_interview_data(interview_id)
            if not interview_data:
                raise Exception(f"Interview {interview_id} not found or has no transcript")

            # 2. Generate AI score report via LLM
            score_report = await self._generate_score_report(
                transcript=interview_data["full_transcript"],
                candidate_name=interview_data["candidate_name"],
                target_role=interview_data["target_role"],
            )

            # 3. Save score to database
            score_id = self._save_score(interview_id, candidate_id, score_report)

            # 4. Mark job as completed
            self.supabase.table("scoring_jobs").update({
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
                "result_score_id": score_id,
            }).eq("id", job_id).execute()

            logger.info("✅ Job %s completed | score_id=%s | final=%s%%",
                        job_id, score_id, score_report.get("final_score"))

            # 5. Refresh Admin Dashboard Materialized View
            try:
                self.supabase.rpc('refresh_admin_dashboard').execute()
                logger.info("Admin dashboard view refreshed successfully.")
            except Exception as rpc_err:
                logger.warning("Failed to refresh admin dashboard view: %s", rpc_err)

        except Exception as e:
            logger.error("❌ Job %s failed: %s", job_id, e, exc_info=True)

            # Mark job as failed
            try:
                self.supabase.table("scoring_jobs").update({
                    "status": "failed",
                    "error_message": str(e)[:500],
                    "completed_at": datetime.utcnow().isoformat(),
                }).eq("id", job_id).execute()
            except Exception:
                pass

    def _fetch_interview_data(self, interview_id: str) -> Optional[Dict]:
        """Fetch interview transcript + candidate info."""
        try:
            result = (
                self.supabase.table("interviews")
                .select("*, candidates(full_name, target_role, years_of_experience, expected_salary)")
                .eq("id", interview_id)
                .execute()
            )

            if not result.data:
                return None

            row = result.data[0]
            transcript = row.get("full_transcript", [])
            candidates_data = row.get("candidates", {})

            if not transcript:
                logger.warning("Interview %s has empty transcript", interview_id)
                return None

            return {
                "full_transcript": transcript,
                "candidate_name": candidates_data.get("full_name", "Unknown"),
                "target_role": candidates_data.get("target_role", "Unknown"),
                "years_of_experience": candidates_data.get("years_of_experience", 0),
                "expected_salary": candidates_data.get("expected_salary", 0),
            }

        except Exception as e:
            logger.error("Failed to fetch interview data: %s", e)
            return None

    async def _generate_score_report(
        self,
        transcript: list,
        candidate_name: str,
        target_role: str,
    ) -> Dict[str, Any]:
        """
        Generate structured AI evaluation report via LLM.
        Returns JSON with scores, strengths, weaknesses, recommendation.
        """
        # Build transcript text
        transcript_text = "\n".join([
            f"{'سارة' if t.get('role') == 'assistant' else 'المتقدم'}: {t.get('content', '')}"
            for t in transcript
        ])

        system_prompt = """You are an expert HR evaluator for Qabalan Bakery (شركة قبلان للصناعات الغذائية).

Analyze this interview transcript and provide a comprehensive evaluation in JSON format.

Your response must be ONLY valid JSON with this structure:
{
  "category_scores": {
    "communication": {"score": 0-100, "rationale": "..."},
    "learning": {"score": 0-100, "rationale": "..."},
    "stability": {"score": 0-100, "rationale": "..."},
    "credibility": {"score": 0-100, "rationale": "..."},
    "adaptability": {"score": 0-100, "rationale": "..."},
    "field_knowledge": {"score": 0-100, "rationale": "..."}
  },
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "weaknesses": ["weakness 1", "weakness 2"],
  "improvement_areas": ["area 1", "area 2"],
  "salary_recommendation": {
    "min": 300,
    "max": 500,
    "fit_score": 0-100,
    "rationale": "..."
  },
  "cultural_fit_score": 0-100,
  "behavioral_flags": ["flag 1"],
  "risk_indicators": ["risk 1"],
  "hire_recommendation": "strongly_recommend|recommend|neutral|not_recommend|reject",
  "hire_confidence": 0-100,
  "next_steps_suggested": ["step 1", "step 2"],
  "bottom_line_summary": "2-3 sentence summary in Arabic"
}

Focus on:
- Communication skills in Jordanian Arabic
- Honesty and credibility of responses
- Work stability indicators
- Technical competency for the bakery role
- Cultural fit with family business values

Be fair but critical. Look for red flags."""

        user_prompt = f"""Candidate: {candidate_name}
Role: {target_role}

Interview Transcript:
{transcript_text}

Provide your evaluation in JSON format only."""

        try:
            response = await self.llm.generate(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
            )

            # Parse JSON response (strip markdown fences if present)
            response_text = response.strip()
            if response_text.startswith("```"):
                parts = response_text.split("```")
                if len(parts) >= 2:
                    response_text = parts[1]
                    if response_text.startswith("json"):
                        response_text = response_text[4:]
                    response_text = response_text.strip()

            score_report = json.loads(response_text)

            # Calculate weighted final score
            cs = score_report.get("category_scores", {})
            final_score = (
                cs.get("communication", {}).get("score", 50) * 0.20 +
                cs.get("learning", {}).get("score", 50) * 0.15 +
                cs.get("stability", {}).get("score", 50) * 0.15 +
                cs.get("credibility", {}).get("score", 50) * 0.20 +
                cs.get("adaptability", {}).get("score", 50) * 0.15 +
                cs.get("field_knowledge", {}).get("score", 50) * 0.15
            )

            score_report["final_score"] = round(final_score, 2)
            score_report["ai_score"] = round(final_score, 2)

            return score_report

        except json.JSONDecodeError as je:
            logger.error("Failed to parse LLM response as JSON: %s", je)
            return self._fallback_report(f"JSON parse error: {je}")
        except Exception as e:
            logger.error("Failed to generate score report: %s", e)
            return self._fallback_report(str(e))

    @staticmethod
    def _fallback_report(error_msg: str) -> Dict[str, Any]:
        """Return a safe fallback score report when LLM scoring fails."""
        return {
            "final_score": 50.0,
            "ai_score": 50.0,
            "category_scores": {
                cat: {"score": 50, "rationale": f"Scoring error: {error_msg[:100]}"}
                for cat in ["communication", "learning", "stability",
                            "credibility", "adaptability", "field_knowledge"]
            },
            "strengths": ["Unable to evaluate — scoring error"],
            "weaknesses": ["Scoring error occurred"],
            "improvement_areas": [],
            "salary_recommendation": {"min": 0, "max": 0, "fit_score": 0, "rationale": "N/A"},
            "cultural_fit_score": 50,
            "behavioral_flags": [],
            "risk_indicators": ["Scoring failed — manual review required"],
            "hire_recommendation": "neutral",
            "hire_confidence": 0,
            "next_steps_suggested": ["Manual review required"],
            "bottom_line_summary": f"فشل التقييم الآلي: {error_msg[:100]}",
        }

    def _save_score(self, interview_id: str, candidate_id: str,
                    score_report: Dict[str, Any]) -> str:
        """Save score report to the scores table. Returns the score ID."""
        cs = score_report.get("category_scores", {})

        score_data = {
            "interview_id": interview_id,
            "candidate_id": candidate_id,
            "final_score": score_report.get("final_score", 50),
            "ai_score": score_report.get("ai_score", 50),

            # Per-category scores
            "communication_score": cs.get("communication", {}).get("score", 50),
            "learning_score": cs.get("learning", {}).get("score", 50),
            "stability_score": cs.get("stability", {}).get("score", 50),
            "credibility_score": cs.get("credibility", {}).get("score", 50),
            "adaptability_score": cs.get("adaptability", {}).get("score", 50),
            "field_knowledge_score": cs.get("field_knowledge", {}).get("score", 50),

            # Detailed JSON
            "category_scores": cs,
            "strengths": score_report.get("strengths", []),
            "weaknesses": score_report.get("weaknesses", []),
            "improvement_areas": score_report.get("improvement_areas", []),

            # Salary
            "salary_recommendation_min": score_report.get("salary_recommendation", {}).get("min"),
            "salary_recommendation_max": score_report.get("salary_recommendation", {}).get("max"),
            "salary_fit_score": score_report.get("salary_recommendation", {}).get("fit_score"),
            "salary_fit_rationale": score_report.get("salary_recommendation", {}).get("rationale"),

            # Fit & Risk
            "cultural_fit_score": score_report.get("cultural_fit_score"),
            "behavioral_flags": score_report.get("behavioral_flags", []),
            "risk_indicators": score_report.get("risk_indicators", []),

            # Recommendation
            "hire_recommendation": score_report.get("hire_recommendation"),
            "hire_confidence": score_report.get("hire_confidence"),
            "next_steps_suggested": score_report.get("next_steps_suggested", []),
            "bottom_line_summary": score_report.get("bottom_line_summary"),

            # Meta
            "scoring_llm_model": "groq/llama-3.3-70b",
            "scoring_llm_temperature": 0.3,
            "scored_at": datetime.utcnow().isoformat(),
        }

        result = self.supabase.table("scores").insert(score_data).execute()

        if result.data and len(result.data) > 0:
            score_id = result.data[0].get("id", "unknown")
            logger.info("Score saved: %s (final=%.1f%%)", score_id, score_report.get("final_score", 0))
            return str(score_id)

        raise Exception("Failed to insert score — no data returned")

    def stop(self):
        """Stop the worker gracefully."""
        self.is_running = False
        logger.info("🛑 Scoring worker stopping...")


async def run_worker():
    """Run the scoring worker."""
    worker = ScoringWorker()
    try:
        await worker.start()
    except KeyboardInterrupt:
        worker.stop()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run_worker())

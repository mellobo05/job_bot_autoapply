"""
AutoApply Bot — Main Orchestrator
Runs the full pipeline every N minutes, 24/7.

Pipeline:
  1. Scrape all 20 ATS platforms for new AI/GenAI remote jobs
  2. Score each JD against resume via AI
  3. ≥80%  → Auto-apply + LinkedIn outreach + tracker
  4. 60-79% → Email to Melanie + tracker
  5. <60%  → Skip
  6. Update Excel tracker after every action
"""

import sys
import time
import logging
import signal
from datetime import datetime
from pathlib import Path
from typing import List, Dict

# ── Ensure project root is on path ──────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import (
    USER, TARGET_ROLES, JOB_PLATFORMS, FILTERS,
    MATCH_AUTO_APPLY, MATCH_EMAIL_REVIEW,
    EMAIL, LINKEDIN, TRACKER, SCHEDULER, AI,
)
from scrapers.scraper      import scrape_all_platforms
from utils.resume_matcher  import extract_resume_text, match_resume_to_jd, quick_keyword_score
from utils.tracker         import log_job
from utils.email_notifier  import send_review_email, send_applied_confirmation
from utils.linkedin_bot    import LinkedInBot

# ── Logging setup ─────────────────────────────────────────────
Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")

# ── Graceful shutdown ─────────────────────────────────────────
_running = True
def _handle_exit(sig, frame):
    global _running
    logger.info("Shutdown signal received — finishing current scan...")
    _running = False
signal.signal(signal.SIGTERM, _handle_exit)
signal.signal(signal.SIGINT,  _handle_exit)


# ═════════════════════════════════════════════════════════════
class AutoApplyBot:

    def __init__(self):
        self.resume_text  = extract_resume_text(USER["resume_path"])
        self.linkedin     = LinkedInBot(LINKEDIN)
        self.review_batch: List[Dict] = []   # collect 60-79% jobs for digest email
        self.scan_count   = 0

        if not self.resume_text:
            logger.warning(
                "⚠  Resume not found at data/resume.pdf — "
                "matching will be skipped. Please add your resume."
            )

    # ── Single scan cycle ────────────────────────────────────
    def run_scan(self):
        self.scan_count += 1
        logger.info(f"{'='*60}")
        logger.info(f"SCAN #{self.scan_count} — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*60}")

        # 1. Scrape
        jobs = scrape_all_platforms(JOB_PLATFORMS, TARGET_ROLES, FILTERS)
        logger.info(f"Total new jobs this scan: {len(jobs)}")

        applied_count = review_count = skip_count = 0

        for job in jobs:
            try:
                score, details = self._score_job(job)
                job["score"]   = score
                job["details"] = details

                if score >= MATCH_AUTO_APPLY:
                    self._handle_auto_apply(job, details)
                    applied_count += 1

                elif score >= MATCH_EMAIL_REVIEW:
                    self._handle_review(job, details)
                    review_count += 1

                else:
                    skip_count += 1
                    logger.debug(f"Skip ({score}%): {job['title']} @ {job['company']}")
                    log_job({**job, "status": "Skipped"}, TRACKER)

            except Exception as e:
                logger.error(f"Error processing {job.get('title')}: {e}")

        # Send batched review email
        if self.review_batch:
            send_review_email(self.review_batch, EMAIL)
            self.review_batch.clear()

        logger.info(
            f"Scan #{self.scan_count} done — "
            f"Applied: {applied_count} | "
            f"Review: {review_count} | "
            f"Skipped: {skip_count}"
        )

    # ── Scoring ───────────────────────────────────────────────
    def _score_job(self, job: Dict):
        """Score the job against the resume. Returns (score, details_dict)."""
        if not self.resume_text:
            return 50, {}

        # Fast keyword pre-check (no API cost)
        jd = job.get("description") or job.get("title") or ""
        quick = quick_keyword_score(self.resume_text, jd)

        # Skip AI call if obviously bad match
        if quick < 30:
            return quick, {"summary": "Keyword pre-filter: low match"}

        # Full AI match
        if not AI.get("api_key"):
            # No API key: use keyword score only
            return quick, {"summary": "Keyword-based score (no API key set)"}

        details = match_resume_to_jd(
            resume_text=self.resume_text,
            jd_text=jd,
            api_key=AI["api_key"],
            model=AI["model"],
        )
        score = details.get("score", quick)
        return score, details

    # ── Auto-apply ────────────────────────────────────────────
    def _handle_auto_apply(self, job: Dict, details: dict):
        logger.info(
            f"✅ AUTO-APPLY ({job['score']}%): "
            f"{job['title']} @ {job['company']} [{job['platform']}]"
        )

        # Attempt application
        success = False
        try:
            from appliers.applier import AutoApplier
            applier = AutoApplier(USER)
            success = applier.apply(job)
        except Exception as e:
            logger.error(f"Applier error: {e}")

        status     = "Auto-Applied" if success else "Apply Failed"
        applied_at = datetime.now().strftime("%Y-%m-%d %H:%M") if success else ""

        # Log to tracker
        log_job({
            **job,
            "status":     status,
            "applied_at": applied_at,
            "notes":      details.get("summary", ""),
        }, TRACKER)

        # Send confirmation email
        if success and EMAIL.get("from_password"):
            send_applied_confirmation({**job, "score": job["score"]}, EMAIL)

        # LinkedIn outreach
        if success:
            self._do_linkedin_outreach(job)

    # ── Review (60-79%) ───────────────────────────────────────
    def _handle_review(self, job: Dict, details: dict):
        logger.info(
            f"📧 REVIEW EMAIL ({job['score']}%): "
            f"{job['title']} @ {job['company']} [{job['platform']}]"
        )
        self.review_batch.append({
            **job,
            "score":          job["score"],
            "matched_skills": details.get("matched_skills", []),
            "missing_skills": details.get("missing_skills", []),
            "summary":        details.get("summary", ""),
        })
        log_job({
            **job,
            "status":     "Review Sent",
            "email_sent": True,
            "notes":      details.get("summary", ""),
        }, TRACKER)

    # ── LinkedIn outreach ─────────────────────────────────────
    def _do_linkedin_outreach(self, job: Dict):
        if not LINKEDIN.get("enabled") or not LINKEDIN.get("password"):
            return
        try:
            person = self.linkedin.find_and_connect(
                company=job.get("company", ""),
                role=job.get("title", ""),
                job_url=job.get("url", ""),
            )
            if person:
                from utils.tracker import update_status
                update_status(
                    url=job["url"],
                    status="Auto-Applied",
                    tracker_config=TRACKER,
                    notes=f"LinkedIn sent to {person['name']} ({person['title']})",
                )
        except Exception as e:
            logger.error(f"LinkedIn outreach error: {e}")

    # ── Continuous loop ────────────────────────────────────────
    def run_forever(self):
        interval = SCHEDULER["scan_interval_minutes"] * 60
        logger.info(
            f"🤖 AutoApply Bot started — "
            f"scanning every {SCHEDULER['scan_interval_minutes']} minutes, 24/7"
        )
        logger.info(f"Platforms: {len(JOB_PLATFORMS)} | Roles: {TARGET_ROLES}")

        while _running:
            try:
                self.run_scan()
            except Exception as e:
                logger.error(f"Scan error: {e}")

            if not _running:
                break

            logger.info(f"💤 Sleeping {SCHEDULER['scan_interval_minutes']}m until next scan...")
            for _ in range(interval):
                if not _running:
                    break
                time.sleep(1)

        logger.info("Bot stopped gracefully.")


# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AutoApply Job Bot")
    parser.add_argument("--once", action="store_true", help="Run one scan then exit")
    args = parser.parse_args()

    bot = AutoApplyBot()
    if args.once:
        bot.run_scan()
    else:
        bot.run_forever()

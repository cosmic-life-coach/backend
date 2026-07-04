"""
Daily recommendation push scheduler.

Once a day (configurable hour, Asia/Kolkata) the backend generates each
user's daily Vedic recommendation and pushes it to their device via FCM.
No frontend involvement beyond registering the token at login
(POST /api/v1/notifications/token).

Uses APScheduler's BackgroundScheduler (thread-based) because our service
layer is synchronous. Started from main.py's startup hook; a failed push
for one user never stops the run for the others.
"""

import json
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from repositories.firestore_user_repository import FirestoreUserRepository
from services.fcm_notification_service import FcmNotificationService
from services.rag_orchestrator import RagOrchestrator

logger = logging.getLogger(__name__)

FALLBACK_TITLE = "Your daily cosmic guidance"


def parse_recommendation_to_push(raw: str) -> tuple[str, str]:
    """
    Convert the raw Gemini daily-recommendation output into (title, body).

    The prompt requests strict JSON (theme/do/avoid/lucky_window/affirmation);
    when Gemini misbehaves we fall back to plain text so the push still sends.
    """
    try:
        cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
        rec = json.loads(cleaned)
        title = str(rec.get("theme") or FALLBACK_TITLE)
        body = str(rec.get("affirmation") or "; ".join(rec.get("do", [])) or "Open the app for today's guidance.")
        return title, body
    except (json.JSONDecodeError, AttributeError, TypeError):
        return FALLBACK_TITLE, (raw.strip()[:180] or "Open the app for today's guidance.")


class DailyNotificationScheduler:
    """Owns the cron job that fans out the daily recommendation pushes."""

    def __init__(
        self,
        users: FirestoreUserRepository,
        rag: RagOrchestrator,
        fcm: FcmNotificationService,
        hour_ist: int,
    ):
        self._users = users
        self._rag = rag
        self._fcm = fcm
        self._hour = hour_ist
        self._scheduler: BackgroundScheduler | None = None

    def start(self) -> None:
        """Schedule the daily job at the configured IST hour and start ticking."""
        self._scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
        self._scheduler.add_job(
            self.run_once,
            CronTrigger(hour=self._hour, minute=0, timezone="Asia/Kolkata"),
            id="daily_recommendation_push",
            coalesce=True,          # missed runs (downtime) collapse into one
            misfire_grace_time=3600,
        )
        self._scheduler.start()
        logger.info("Daily push scheduled for %02d:00 IST", self._hour)

    def shutdown(self) -> None:
        """Stop the scheduler cleanly on app shutdown."""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)

    def run_once(self) -> dict:
        """
        Generate + push today's recommendation to every user with a token.

        Per-user failures are logged and skipped so one bad token or LLM
        hiccup never blocks the rest. Returns {sent, failed} counts.
        """
        sent = failed = 0
        for uid in self._users.list_uids_with_fcm_token():
            try:
                raw = self._rag.daily_recommendation(uid, calendar_events_text="")
                title, body = parse_recommendation_to_push(raw)
                self._fcm.send_to_user(uid, title, body, data={"type": "daily_recommendation"})
                sent += 1
            except Exception as exc:
                failed += 1
                logger.warning("Daily push failed for %s: %s", uid, exc)
        logger.info("Daily push run complete: %d sent, %d failed", sent, failed)
        return {"sent": sent, "failed": failed}

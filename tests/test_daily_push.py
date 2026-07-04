"""Unit tests for the daily recommendation push scheduler (PR: daily-recommendation-push)."""

from services.daily_notification_scheduler import (
    DailyNotificationScheduler,
    FALLBACK_TITLE,
    parse_recommendation_to_push,
)


def test_parse_valid_json():
    """Well-formed Gemini JSON becomes (theme, affirmation)."""
    raw = '{"theme": "Focus", "do": ["meditate"], "affirmation": "I am steady."}'
    title, body = parse_recommendation_to_push(raw)
    assert title == "Focus"
    assert body == "I am steady."


def test_parse_json_in_markdown_fences():
    """Gemini often wraps JSON in ```json fences -- must still parse."""
    raw = '```json\n{"theme": "Rest", "affirmation": "I recharge."}\n```'
    title, body = parse_recommendation_to_push(raw)
    assert (title, body) == ("Rest", "I recharge.")


def test_parse_garbage_falls_back():
    """Non-JSON output still produces a sendable push."""
    title, body = parse_recommendation_to_push("The stars say hello")
    assert title == FALLBACK_TITLE
    assert body == "The stars say hello"


class _Users:
    def list_uids_with_fcm_token(self):
        return ["u1", "u2", "u3"]


class _Rag:
    def daily_recommendation(self, uid, calendar_events_text):
        if uid == "u2":
            raise RuntimeError("gemini hiccup")
        return '{"theme": "Go", "affirmation": "Onward."}'


class _Fcm:
    def __init__(self):
        self.sent = []

    def send_to_user(self, uid, title, body, data=None):
        self.sent.append((uid, title, body))
        return f"msg_{uid}"


def test_run_once_isolates_per_user_failures():
    """One user's failure must not stop the fan-out; counts are accurate."""
    fcm = _Fcm()
    scheduler = DailyNotificationScheduler(_Users(), _Rag(), fcm, hour_ist=7)

    result = scheduler.run_once()

    assert result == {"sent": 2, "failed": 1}
    assert [s[0] for s in fcm.sent] == ["u1", "u3"]
    assert fcm.sent[0][1] == "Go"

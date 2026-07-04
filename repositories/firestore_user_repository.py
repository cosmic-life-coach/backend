"""
Firestore repository (Repository pattern).

All static user data lives under the root /users collection where the
document ID is exactly the Firebase Auth `uid` -- the global partition key.

Document layout:
    /users/{uid}
        profile:        {name, dob, birth_time, birth_place, lat, lon, tz_offset}
        fcm_token:      str            (device push token from the Flutter app)
        chat_counters:  {chat_title: int}   (per-chat message counter)
        integrations:
            google_calendar: {token, refresh_token, ...}  (OAuth credentials)
"""

import logging

from google.api_core import exceptions as gexc

from utils.error_handlers import ServiceUnavailableError

logger = logging.getLogger(__name__)


class FirestoreUserRepository:
    """CRUD operations for /users/{uid} documents."""

    def __init__(self, db):
        """`db` is a firestore.Client created once at app startup."""
        self._db = db

    def _user_ref(self, uid: str):
        """Return the DocumentReference for a user's root document."""
        return self._db.collection("users").document(uid)

    def get_profile(self, uid: str) -> dict | None:
        """Fetch the user's profile map, or None if not set."""
        try:
            snap = self._user_ref(uid).get()
        except (gexc.GoogleAPICallError, gexc.RetryError) as exc:
            raise ServiceUnavailableError("Firestore", exc) from exc
        return snap.to_dict().get("profile") if snap.exists else None

    def save_profile(self, uid: str, profile: dict) -> None:
        """Create or merge the user's birth-details profile."""
        try:
            self._user_ref(uid).set({"profile": profile}, merge=True)
        except (gexc.GoogleAPICallError, gexc.RetryError) as exc:
            raise ServiceUnavailableError("Firestore", exc) from exc

    def get_fcm_token(self, uid: str) -> str | None:
        """Return the user's registered FCM device token, if any."""
        try:
            snap = self._user_ref(uid).get()
        except (gexc.GoogleAPICallError, gexc.RetryError) as exc:
            raise ServiceUnavailableError("Firestore", exc) from exc
        return snap.to_dict().get("fcm_token") if snap.exists else None

    def save_fcm_token(self, uid: str, token: str) -> None:
        """Store/replace the FCM device token sent by the Flutter client."""
        try:
            self._user_ref(uid).set({"fcm_token": token}, merge=True)
        except (gexc.GoogleAPICallError, gexc.RetryError) as exc:
            raise ServiceUnavailableError("Firestore", exc) from exc

    def next_chat_number(self, uid: str, chat_title: str) -> int:
        """
        Atomically increment and return the message counter for a chat title.
        Used to build vector IDs: uid_chat_title_chatnumber.
        """
        from google.cloud import firestore as gcf

        ref = self._user_ref(uid)
        try:
            ref.set({"chat_counters": {chat_title: gcf.Increment(1)}}, merge=True)
            snap = ref.get()
            return int(snap.to_dict()["chat_counters"][chat_title])
        except (gexc.GoogleAPICallError, gexc.RetryError) as exc:
            raise ServiceUnavailableError("Firestore", exc) from exc

    def get_chart_insights(self, uid: str) -> dict | None:
        """Return the stored Gemini chart interpretation, if generated."""
        try:
            snap = self._user_ref(uid).get()
        except (gexc.GoogleAPICallError, gexc.RetryError) as exc:
            raise ServiceUnavailableError("Firestore", exc) from exc
        return snap.to_dict().get("chart_insights") if snap.exists else None

    def save_chart_insights(self, uid: str, insights: dict) -> None:
        """Persist the Gemini chart interpretation alongside the profile."""
        try:
            self._user_ref(uid).set({"chart_insights": insights}, merge=True)
        except (gexc.GoogleAPICallError, gexc.RetryError) as exc:
            raise ServiceUnavailableError("Firestore", exc) from exc

    def get_calendar_credentials(self, uid: str) -> dict | None:
        """Return stored Google Calendar OAuth credentials for this user."""
        try:
            snap = self._user_ref(uid).get()
        except (gexc.GoogleAPICallError, gexc.RetryError) as exc:
            raise ServiceUnavailableError("Firestore", exc) from exc
        if not snap.exists:
            return None
        return snap.to_dict().get("integrations", {}).get("google_calendar")

    def save_calendar_credentials(self, uid: str, creds: dict) -> None:
        """Persist Google Calendar OAuth credentials under the user document."""
        try:
            self._user_ref(uid).set(
                {"integrations": {"google_calendar": creds}}, merge=True
            )
        except (gexc.GoogleAPICallError, gexc.RetryError) as exc:
            raise ServiceUnavailableError("Firestore", exc) from exc

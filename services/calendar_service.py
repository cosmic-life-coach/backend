"""
Google Calendar service (read + write).

OAuth flow:
    1. GET /calendar/oauth/url        -> user opens Google's consent screen
    2. Google redirects to /calendar/oauth/callback?code=...&state=<uid>
    3. Tokens are stored per-user in Firestore under
       /users/{uid}.integrations.google_calendar

After connection: list a day's events and create new events on the
user's primary calendar.
"""

import logging
from datetime import datetime, time, timedelta

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from config.settings import get_settings
from repositories.firestore_user_repository import FirestoreUserRepository
from utils.error_handlers import ServiceUnavailableError

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


class CalendarService:
    """Per-user Google Calendar reads and writes with Firestore-stored tokens."""

    def __init__(self, users: FirestoreUserRepository):
        self._users = users
        self._settings = get_settings()

    # ---------- OAuth ----------

    def _flow(self) -> Flow:
        """Build the OAuth flow object from client credentials in .env.local."""
        client_config = {
            "web": {
                "client_id": self._settings.google_oauth_client_id,
                "client_secret": self._settings.google_oauth_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self._settings.google_oauth_redirect_uri],
            }
        }
        return Flow.from_client_config(
            client_config, scopes=SCOPES,
            redirect_uri=self._settings.google_oauth_redirect_uri,
        )

    def get_authorization_url(self, uid: str) -> str:
        """Return Google's consent URL; `state` carries the uid across redirect."""
        url, _ = self._flow().authorization_url(
            access_type="offline", prompt="consent", state=uid
        )
        return url

    def handle_oauth_callback(self, uid: str, code: str) -> None:
        """Exchange the authorization code for tokens and persist them."""
        try:
            flow = self._flow()
            flow.fetch_token(code=code)
            creds = flow.credentials
        except Exception as exc:
            raise ServiceUnavailableError("Google OAuth", exc) from exc

        self._users.save_calendar_credentials(uid, {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes or SCOPES),
        })

    def _credentials(self, uid: str) -> Credentials:
        """Load stored credentials, refreshing the access token if expired."""
        stored = self._users.get_calendar_credentials(uid)
        if not stored:
            raise ValueError(
                "Google Calendar is not connected for this user. "
                "Call GET /api/v1/calendar/oauth/url first."
            )
        creds = Credentials(**stored)
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleAuthRequest())
        return creds

    # ---------- Read / Write ----------

    def list_events(self, uid: str, day: datetime) -> list[dict]:
        """Return the user's primary-calendar events for one calendar day."""
        creds = self._credentials(uid)
        start = datetime.combine(day.date(), time.min).isoformat() + "Z"
        end = (datetime.combine(day.date(), time.min) + timedelta(days=1)).isoformat() + "Z"
        try:
            service = build("calendar", "v3", credentials=creds, cache_discovery=False)
            result = service.events().list(
                calendarId="primary", timeMin=start, timeMax=end,
                singleEvents=True, orderBy="startTime",
            ).execute()
        except Exception as exc:
            raise ServiceUnavailableError("Google Calendar", exc) from exc

        return [
            {
                "id": e.get("id"),
                "title": e.get("summary", "(no title)"),
                "start": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
                "end": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date"),
                "description": e.get("description"),
            }
            for e in result.get("items", [])
        ]

    def create_event(
        self, uid: str, title: str, start_iso: str, end_iso: str,
        description: str | None = None, timezone: str = "Asia/Kolkata",
    ) -> dict:
        """Create an event on the user's primary calendar; returns id + link."""
        creds = self._credentials(uid)
        body = {
            "summary": title,
            "description": description or "",
            "start": {"dateTime": start_iso, "timeZone": timezone},
            "end": {"dateTime": end_iso, "timeZone": timezone},
        }
        try:
            service = build("calendar", "v3", credentials=creds, cache_discovery=False)
            created = service.events().insert(calendarId="primary", body=body).execute()
        except Exception as exc:
            raise ServiceUnavailableError("Google Calendar", exc) from exc

        return {"id": created.get("id"), "html_link": created.get("htmlLink")}

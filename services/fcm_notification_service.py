"""
FCM push notification service.

Reads the target user's FCM device token from Firestore (/users/{uid})
and sends a push notification through Firebase Cloud Messaging via the
Admin SDK (`messaging.send`).
"""

import logging

from repositories.firestore_user_repository import FirestoreUserRepository
from utils.error_handlers import ServiceUnavailableError

logger = logging.getLogger(__name__)


class FcmNotificationService:
    """Sends push notifications to a specific user's registered device."""

    def __init__(self, users: FirestoreUserRepository):
        self._users = users

    def send_to_user(
        self, uid: str, title: str, body: str, data: dict[str, str] | None = None
    ) -> str:
        """
        Send a push notification to the user identified by `uid`.

        Steps:
            1. Look up the user's FCM token in Firestore.
            2. Build an FCM Message (notification + optional data payload).
            3. Dispatch with firebase_admin.messaging.send().

        Returns:
            The FCM message ID on success.

        Raises:
            ValueError: If the user has no registered FCM token.
            ServiceUnavailableError: If FCM itself cannot be reached.
        """
        token = self._users.get_fcm_token(uid)
        if not token:
            raise ValueError(f"No FCM token registered for user '{uid}'.")

        from firebase_admin import messaging  # lazy import (testability)

        message = messaging.Message(
            token=token,
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
        )
        try:
            message_id = messaging.send(message)
        except Exception as exc:
            raise ServiceUnavailableError("Firebase Cloud Messaging", exc) from exc

        logger.info("FCM sent to %s: %s", uid, message_id)
        return message_id

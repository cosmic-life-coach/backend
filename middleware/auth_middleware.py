"""
Firebase authentication middleware.

Captures the incoming `Authorization: Bearer <idToken>` header from the
Flutter client, verifies it with the Firebase Admin SDK, and stores the
global `uid` on `request.state.uid` for every downstream handler.

Public paths (docs, health, OAuth callback) bypass verification.
"""

import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from utils.error_handlers import error_envelope

logger = logging.getLogger(__name__)

# Paths reachable without a Firebase ID token.
PUBLIC_PATHS = {
    "/",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/v1/calendar/oauth/callback",  # Google redirects here without our token
}


class FirebaseAuthMiddleware(BaseHTTPMiddleware):
    """Validates Firebase ID tokens and injects `uid` into request state."""

    async def dispatch(self, request: Request, call_next):
        """Verify Bearer token unless the path is public; else return 401."""
        if request.url.path in PUBLIC_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content=error_envelope(
                    code="MISSING_TOKEN",
                    message="Authorization header with a Bearer token is required.",
                ),
            )

        id_token = auth_header.removeprefix("Bearer ").strip()
        try:
            # Imported lazily so unit tests can run without Firebase initialized.
            from firebase_admin import auth as firebase_auth

            decoded = firebase_auth.verify_id_token(id_token)
            request.state.uid = decoded["uid"]
        except Exception as exc:  # invalid, expired, revoked, or Firebase down
            logger.warning("Token verification failed: %s", exc)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content=error_envelope(
                    code="INVALID_TOKEN",
                    message="Firebase ID token is invalid or expired. Please sign in again.",
                ),
            )

        return await call_next(request)


def get_current_uid(request: Request) -> str:
    """FastAPI dependency: return the uid set by the middleware."""
    return request.state.uid

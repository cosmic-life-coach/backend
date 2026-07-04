"""
Global error handling.

Every error leaves the API in one consistent envelope so the Flutter client
can always parse `error.code` and `error.message`:

    {"success": false, "error": {"code": "...", "message": "...", "detail": ...}}

Unreachable backends (Firestore / Pinecone / Gemini / Google Calendar) map to
HTTP 503 with a message naming exactly which service is down.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ServiceUnavailableError(Exception):
    """Raised when an upstream dependency (DB / LLM / API) cannot be reached."""

    def __init__(self, service_name: str, original: Exception | None = None):
        self.service_name = service_name
        self.original = original
        super().__init__(f"{service_name} is not reachable.")


def error_envelope(code: str, message: str, detail=None) -> dict:
    """Build the standard error payload used by every handler below."""
    return {"success": False, "error": {"code": code, "message": message, "detail": detail}}


def register_error_handlers(app: FastAPI) -> None:
    """Attach all global exception handlers to the FastAPI app."""

    @app.exception_handler(ServiceUnavailableError)
    async def handle_service_unavailable(request: Request, exc: ServiceUnavailableError):
        """503 -- an external backend (Firestore, Pinecone, Gemini...) is down."""
        logger.error("Upstream failure: %s (%s)", exc.service_name, exc.original)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_envelope(
                code="SERVICE_UNAVAILABLE",
                message=f"Backend not connected: {exc.service_name} is unreachable. "
                        "Please try again shortly.",
                detail=str(exc.original) if exc.original else None,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        """Pass through explicit HTTP errors (401, 404...) in the envelope."""
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(code=f"HTTP_{exc.status_code}", message=str(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        """422 -- request body/query failed Pydantic validation."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_envelope(
                code="VALIDATION_ERROR",
                message="Request payload is invalid.",
                detail=exc.errors(),
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        """500 -- catch-all so the client never receives a raw stack trace."""
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_envelope(
                code="INTERNAL_ERROR",
                message="Something went wrong on the server. The issue has been logged.",
            ),
        )

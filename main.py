"""
Application entry point.

Wires together settings validation, Firebase initialization, auth middleware,
global error handlers, and all /api/v1 routers. Swagger UI is served at /docs.

Run locally:
    uvicorn main:app --reload
"""

import logging
import sys

from fastapi import FastAPI

from config.settings import get_settings
from middleware.auth_middleware import FirebaseAuthMiddleware
from routers import (
    calendar_router,
    chat_router,
    daily_recommendation_router,
    notification_router,
    user_profile_router,
)
from utils.error_handlers import register_error_handlers


def create_app() -> FastAPI:
    """
    Build and return the FastAPI application.

    Fails fast with a readable message if .env.local is missing keys or the
    Firebase service-account file cannot be found.
    """
    try:
        settings = get_settings()
    except Exception as exc:
        sys.exit(f"[startup] Missing/invalid configuration in .env.local:\n{exc}")

    logging.basicConfig(level=settings.log_level)

    app = FastAPI(
        title="Vedic Life Coach API",
        version="1.0.0",
        description=(
            "FastAPI backend for the Daily Life Coach app: Vedic astrology "
            "(Swiss Ephemeris) + Gemini RAG over Pinecone, Firebase auth, "
            "Google Calendar and FCM push notifications."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Firebase must be initialized before the first token verification.
    from dependencies import init_firebase

    try:
        init_firebase()
    except Exception as exc:
        sys.exit(f"[startup] Firebase initialization failed: {exc}")

    app.add_middleware(FirebaseAuthMiddleware)
    register_error_handlers(app)

    app.include_router(chat_router.router)
    app.include_router(user_profile_router.router)
    app.include_router(daily_recommendation_router.router)
    app.include_router(calendar_router.router)
    app.include_router(notification_router.router)

    @app.get("/health", tags=["System"], summary="Liveness probe")
    async def health():
        """Unauthenticated liveness check for the Flutter client / infra."""
        return {"success": True, "status": "ok", "env": settings.app_env}

    # --- Daily recommendation push (FCM) ---------------------------------
    # Started via startup hook so it only runs when the server actually
    # serves (unit tests build the app without firing lifespan events).
    if settings.daily_push_enabled:

        @app.on_event("startup")
        async def start_daily_push_scheduler():
            """Wire the scheduler from the singleton services and start it."""
            from dependencies import (
                get_fcm_service,
                get_rag_orchestrator,
                get_user_repository,
            )
            from services.daily_notification_scheduler import DailyNotificationScheduler

            app.state.daily_scheduler = DailyNotificationScheduler(
                users=get_user_repository(),
                rag=get_rag_orchestrator(),
                fcm=get_fcm_service(),
                hour_ist=settings.daily_push_hour_ist,
            )
            app.state.daily_scheduler.start()

        @app.on_event("shutdown")
        async def stop_daily_push_scheduler():
            """Stop cron threads cleanly when the server exits."""
            scheduler = getattr(app.state, "daily_scheduler", None)
            if scheduler:
                scheduler.shutdown()

    return app


app = create_app()

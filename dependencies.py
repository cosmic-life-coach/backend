"""
Dependency wiring (composition root).

Creates each external client exactly once per process and exposes
FastAPI-injectable factories for repositories and services. Routers never
construct clients themselves -- they only declare what they need.
"""

from functools import lru_cache

from config.settings import get_settings
from repositories.firestore_user_repository import FirestoreUserRepository
from repositories.pinecone_memory_handler import PineconeMemoryHandler
from services.calendar_service import CalendarService
from services.fcm_notification_service import FcmNotificationService
from services.gemini_service import GeminiService
from services.rag_orchestrator import RagOrchestrator


def init_firebase() -> None:
    """Initialize the Firebase Admin app once, at startup (idempotent)."""
    import firebase_admin
    from firebase_admin import credentials

    if not firebase_admin._apps:
        settings = get_settings()
        settings.validate_service_account_file()
        cred = credentials.Certificate(settings.firebase_service_account_path)
        firebase_admin.initialize_app(cred)


@lru_cache
def get_user_repository() -> FirestoreUserRepository:
    """Singleton Firestore repository (client created on first use)."""
    from firebase_admin import firestore

    from utils.error_handlers import ServiceUnavailableError

    try:
        init_firebase()
        return FirestoreUserRepository(firestore.client())
    except Exception as exc:  # client construction failure -> clean 503
        raise ServiceUnavailableError("Firestore", exc) from exc


@lru_cache
def get_memory_handler() -> PineconeMemoryHandler:
    """Singleton Pinecone repository bound to the configured index."""
    from pinecone import Pinecone

    from utils.error_handlers import ServiceUnavailableError

    settings = get_settings()
    try:
        pc = Pinecone(api_key=settings.pinecone_api_key)
        return PineconeMemoryHandler(pc.Index(settings.pinecone_index_name))
    except Exception as exc:  # client construction failure -> clean 503
        raise ServiceUnavailableError("Pinecone", exc) from exc


@lru_cache
def get_gemini_service() -> GeminiService:
    """Singleton Gemini service."""
    return GeminiService()


@lru_cache
def get_rag_orchestrator() -> RagOrchestrator:
    """Singleton RAG orchestrator composed from the singletons above."""
    return RagOrchestrator(
        gemini=get_gemini_service(),
        memory=get_memory_handler(),
        users=get_user_repository(),
    )


@lru_cache
def get_calendar_service() -> CalendarService:
    """Singleton Google Calendar service."""
    return CalendarService(users=get_user_repository())


@lru_cache
def get_fcm_service() -> FcmNotificationService:
    """Singleton FCM notification service."""
    return FcmNotificationService(users=get_user_repository())

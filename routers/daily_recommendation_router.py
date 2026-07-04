"""Daily recommendation endpoint: chart + today's calendar -> Gemini guidance."""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Request

from dependencies import get_calendar_service, get_rag_orchestrator
from middleware.auth_middleware import get_current_uid
from services.calendar_service import CalendarService
from services.rag_orchestrator import RagOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/recommendations", tags=["Daily Recommendation"])


@router.get("/daily", summary="Get today's Vedic daily recommendation")
async def daily_recommendation(
    request: Request,
    rag: RagOrchestrator = Depends(get_rag_orchestrator),
    calendar: CalendarService = Depends(get_calendar_service),
):
    """
    Build today's guidance from the user's birth chart and calendar.

    Calendar is optional context: if the user hasn't connected Google
    Calendar, the recommendation still works with chart data alone.
    """
    uid = get_current_uid(request)

    events_text = ""
    try:
        events = calendar.list_events(uid, datetime.now())
        events_text = "\n".join(f"- {e['title']} ({e['start']})" for e in events)
    except Exception as exc:  # calendar not connected / unreachable -> degrade
        logger.info("Calendar unavailable for %s: %s", uid, exc)

    raw = rag.daily_recommendation(uid, events_text)

    try:  # the prompt asks Gemini for strict JSON; fall back to raw text
        cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
        recommendation = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        recommendation = {"theme": raw}

    return {"success": True, "recommendation": recommendation}

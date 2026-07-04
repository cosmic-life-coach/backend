"""Google Calendar endpoints: OAuth connect, list events, create events."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from dependencies import get_calendar_service
from middleware.auth_middleware import get_current_uid
from schemas.calendar_schemas import CalendarEvent, CalendarEventCreateRequest
from services.calendar_service import CalendarService

router = APIRouter(prefix="/api/v1/calendar", tags=["Calendar"])


@router.get("/oauth/url", summary="Get Google consent URL to connect calendar")
async def oauth_url(
    request: Request,
    calendar: CalendarService = Depends(get_calendar_service),
):
    """Flutter opens this URL in a browser; state carries the uid back."""
    uid = get_current_uid(request)
    return {"success": True, "authorization_url": calendar.get_authorization_url(uid)}


@router.get("/oauth/callback", summary="Google OAuth redirect target", include_in_schema=False)
async def oauth_callback(
    code: str,
    state: str,
    calendar: CalendarService = Depends(get_calendar_service),
):
    """Public path (no Bearer token): `state` holds the uid we sent out."""
    calendar.handle_oauth_callback(uid=state, code=code)
    return {"success": True, "message": "Google Calendar connected. You can close this tab."}


@router.get("/events", summary="List events for a day", response_model=list[CalendarEvent])
async def list_events(
    request: Request,
    date: str = Query(default=None, description="YYYY-MM-DD; defaults to today"),
    calendar: CalendarService = Depends(get_calendar_service),
):
    """Read the user's primary-calendar events for the given day."""
    uid = get_current_uid(request)
    day = datetime.fromisoformat(date) if date else datetime.now()
    try:
        return calendar.list_events(uid, day)
    except ValueError as exc:  # calendar not connected yet
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/events", summary="Create a calendar event", status_code=status.HTTP_201_CREATED)
async def create_event(
    body: CalendarEventCreateRequest,
    request: Request,
    calendar: CalendarService = Depends(get_calendar_service),
):
    """Write an event (e.g. a scheduled remedy/ritual) to the user's calendar."""
    uid = get_current_uid(request)
    try:
        created = calendar.create_event(
            uid, body.title, body.start, body.end, body.description, body.timezone
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return {"success": True, "event": created}

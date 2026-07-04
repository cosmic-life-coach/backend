"""Pydantic schemas for Google Calendar endpoints."""

from pydantic import BaseModel, Field


class CalendarEventCreateRequest(BaseModel):
    """Body of POST /api/v1/calendar/events."""

    title: str = Field(..., min_length=1, max_length=200)
    start: str = Field(..., description="ISO-8601 start datetime", examples=["2026-07-05T09:00:00"])
    end: str = Field(..., description="ISO-8601 end datetime", examples=["2026-07-05T09:30:00"])
    description: str | None = Field(default=None, max_length=2000)
    timezone: str = Field(default="Asia/Kolkata")


class CalendarEvent(BaseModel):
    """One event returned by GET /api/v1/calendar/events."""

    id: str | None = None
    title: str
    start: str | None = None
    end: str | None = None
    description: str | None = None

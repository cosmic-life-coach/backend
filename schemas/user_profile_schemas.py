"""Pydantic schemas for user birth-profile endpoints."""

from pydantic import BaseModel, Field


class UserProfileRequest(BaseModel):
    """Birth details needed to compute the Vedic chart."""

    name: str = Field(..., min_length=1, max_length=100)
    dob: str = Field(..., description="Date of birth, ISO format", examples=["1998-03-21"])
    birth_time: str = Field(..., description="Local time of birth HH:MM[:SS]", examples=["14:35"])
    birth_place: str = Field(..., examples=["Jaipur, India"])
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    tz_offset: float = Field(..., ge=-12, le=14, description="UTC offset hours", examples=[5.5])


class UserProfileResponse(BaseModel):
    """Stored profile plus the computed chart summary."""

    success: bool = True
    profile: UserProfileRequest
    chart_summary: str

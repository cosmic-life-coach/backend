"""User birth-profile endpoints: save details, get profile + computed chart."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status

from dependencies import get_user_repository
from middleware.auth_middleware import get_current_uid
from repositories.firestore_user_repository import FirestoreUserRepository
from schemas.user_profile_schemas import UserProfileRequest, UserProfileResponse
from services.astrology_engine_service import compute_birth_chart, summarize_chart_for_prompt

router = APIRouter(prefix="/api/v1/users/me", tags=["User Profile"])


def _chart_summary(profile: dict) -> str:
    """Compute the Vedic chart summary from a stored profile dict."""
    birth_dt = datetime.fromisoformat(f"{profile['dob']}T{profile['birth_time']}")
    chart = compute_birth_chart(
        birth_dt, profile["tz_offset"], profile["lat"], profile["lon"]
    )
    return summarize_chart_for_prompt(chart)


@router.post("/profile", summary="Save birth details", response_model=UserProfileResponse)
async def save_profile(
    body: UserProfileRequest,
    request: Request,
    users: FirestoreUserRepository = Depends(get_user_repository),
):
    """Validate + store birth details in /users/{uid}, return computed chart."""
    uid = get_current_uid(request)
    profile = body.model_dump()

    try:  # verify the chart is computable before persisting bad data
        summary = _chart_summary(profile)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Birth details could not produce a valid chart. "
                   "Check dob (YYYY-MM-DD), birth_time (HH:MM) and coordinates.",
        )

    users.save_profile(uid, profile)
    return UserProfileResponse(profile=body, chart_summary=summary)


@router.get("/profile", summary="Get profile + chart", response_model=UserProfileResponse)
async def get_profile(
    request: Request,
    users: FirestoreUserRepository = Depends(get_user_repository),
):
    """Return the stored profile and freshly computed chart summary."""
    uid = get_current_uid(request)
    profile = users.get_profile(uid)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile saved yet. POST birth details to /api/v1/users/me/profile.",
        )
    return UserProfileResponse(
        profile=UserProfileRequest(**profile), chart_summary=_chart_summary(profile)
    )

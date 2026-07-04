"""User birth-profile endpoints: save details, get profile + computed chart.

The chart is computed deterministically by the Swiss Ephemeris engine and
returned as BOTH structured JSON (for the Flutter chart UI) and a text
summary (for LLM prompts). On save, Gemini generates interpretation JSON
(insights) which is stored in Firestore -- fail-soft: an LLM outage never
blocks a profile save.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status

from dependencies import get_rag_orchestrator, get_user_repository
from middleware.auth_middleware import get_current_uid
from repositories.firestore_user_repository import FirestoreUserRepository
from schemas.user_profile_schemas import UserProfileRequest, UserProfileResponse
from services.astrology_engine_service import compute_birth_chart, summarize_chart_for_prompt
from services.rag_orchestrator import RagOrchestrator

router = APIRouter(prefix="/api/v1/users/me", tags=["User Profile"])


def _compute_chart(profile: dict) -> tuple[dict, str]:
    """Compute the structured Vedic chart + its prompt summary from a profile."""
    birth_dt = datetime.fromisoformat(f"{profile['dob']}T{profile['birth_time']}")
    chart = compute_birth_chart(
        birth_dt, profile["tz_offset"], profile["lat"], profile["lon"]
    )
    return chart, summarize_chart_for_prompt(chart)


@router.post("/profile", summary="Save birth details", response_model=UserProfileResponse)
async def save_profile(
    body: UserProfileRequest,
    request: Request,
    users: FirestoreUserRepository = Depends(get_user_repository),
    rag: RagOrchestrator = Depends(get_rag_orchestrator),
):
    """
    Validate + store birth details in /users/{uid}.

    Pipeline: verify the chart computes -> persist profile -> ask Gemini for
    interpretation JSON (soft-fail) -> persist insights -> return everything.
    """
    uid = get_current_uid(request)
    profile = body.model_dump()

    try:  # verify the chart is computable before persisting bad data
        chart, summary = _compute_chart(profile)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Birth details could not produce a valid chart. "
                   "Check dob (YYYY-MM-DD), birth_time (HH:MM) and coordinates.",
        )

    users.save_profile(uid, profile)

    # Gemini interprets the computed chart; None on failure (never blocks save).
    insights = rag.chart_insights(summary)
    if insights:
        users.save_chart_insights(uid, insights)

    return UserProfileResponse(
        profile=body, chart_summary=summary, chart=chart, insights=insights
    )


@router.get("/profile", summary="Get profile + chart", response_model=UserProfileResponse)
async def get_profile(
    request: Request,
    users: FirestoreUserRepository = Depends(get_user_repository),
):
    """Return the stored profile, freshly computed chart, and stored insights."""
    uid = get_current_uid(request)
    profile = users.get_profile(uid)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile saved yet. POST birth details to /api/v1/users/me/profile.",
        )
    chart, summary = _compute_chart(profile)
    return UserProfileResponse(
        profile=UserProfileRequest(**profile),
        chart_summary=summary,
        chart=chart,
        insights=users.get_chart_insights(uid),
    )

"""Pydantic schemas for FCM notification endpoints."""

from pydantic import BaseModel, Field


class FcmTokenRegisterRequest(BaseModel):
    """Body of POST /api/v1/notifications/token (device registers its token)."""

    fcm_token: str = Field(..., min_length=10)


class NotificationSendRequest(BaseModel):
    """Body of POST /api/v1/notifications/send."""

    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=1000)
    data: dict[str, str] | None = Field(default=None, description="Optional key/value payload")


class NotificationSendResponse(BaseModel):
    """FCM dispatch confirmation."""

    success: bool = True
    message_id: str

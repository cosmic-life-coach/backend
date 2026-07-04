"""FCM endpoints: register a device token, send a push to the current user."""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from dependencies import get_fcm_service, get_user_repository
from middleware.auth_middleware import get_current_uid
from repositories.firestore_user_repository import FirestoreUserRepository
from schemas.notification_schemas import (
    FcmTokenRegisterRequest,
    NotificationSendRequest,
    NotificationSendResponse,
)
from services.fcm_notification_service import FcmNotificationService

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


@router.post("/token", summary="Register this device's FCM token")
async def register_token(
    body: FcmTokenRegisterRequest,
    request: Request,
    users: FirestoreUserRepository = Depends(get_user_repository),
):
    """Flutter calls this after obtaining its FCM token; stored in /users/{uid}."""
    uid = get_current_uid(request)
    users.save_fcm_token(uid, body.fcm_token)
    return {"success": True, "message": "FCM token registered."}


@router.post(
    "/send",
    summary="Send a push notification to the current user",
    response_model=NotificationSendResponse,
)
async def send_notification(
    body: NotificationSendRequest,
    request: Request,
    fcm: FcmNotificationService = Depends(get_fcm_service),
):
    """Read the user's token from Firestore and dispatch via FCM send()."""
    uid = get_current_uid(request)
    try:
        message_id = fcm.send_to_user(uid, body.title, body.body, body.data)
    except ValueError as exc:  # no token registered
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return NotificationSendResponse(message_id=message_id)

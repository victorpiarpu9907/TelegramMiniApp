from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from backend.config import (
    BOT_TOKEN,
    ADMIN_TELEGRAM_ID,
    APP_SECRET
)

from backend.services.telegram_auth import (
    validate_telegram_init_data,
    issue_access_token,
    verify_access_token,
    ACCESS_TOKEN_TTL
)


router = APIRouter(prefix="/api/auth", tags=["authentication"])

security = HTTPBearer(auto_error=False)


class TelegramAuthRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16384)


def get_admin_id() -> int:

    try:
        admin_id = int(ADMIN_TELEGRAM_ID)
        if admin_id <= 0:
            raise ValueError
        return admin_id
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=503,
            detail="Administrator configuration unavailable"
        )


@router.post("/telegram")
def authenticate_telegram(payload: TelegramAuthRequest):

    if not BOT_TOKEN or not APP_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured"
        )

    admin_id = get_admin_id()

    try:
        user = validate_telegram_init_data(
            payload.init_data,
            BOT_TOKEN
        )
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid Telegram authentication"
        )

    if user["id"] != admin_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    access_token = issue_access_token(
        user_id=user["id"],
        app_secret=APP_SECRET
    )

    return {
        "authenticated": True,
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_TTL,
        "user": {
            "id": user["id"],
            "first_name": user.get("first_name", ""),
            "username": user.get("username")
        }
    }


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security)
):

    if not APP_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured"
        )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )

    try:
        payload = verify_access_token(
            credentials.credentials,
            APP_SECRET
        )
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session"
        )

    admin_id = get_admin_id()

    if payload["sub"] != str(admin_id):
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    return {"id": admin_id}


@router.get("/me")
def get_current_user(admin: dict = Depends(require_admin)):

    return {
        "authenticated": True,
        "user_id": admin["id"],
        "role": "administrator"
    }

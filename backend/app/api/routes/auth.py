from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.auth import CaptchaResponse, LoginRequest, LoginResponse
from app.security import create_access_token
from app.services.auth_service import authenticate_user
from app.services.captcha_service import create_captcha_challenge, verify_captcha

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/captcha", response_model=CaptchaResponse)
async def get_captcha() -> CaptchaResponse:
    challenge = create_captcha_challenge()
    return CaptchaResponse(
        captcha_token=challenge.captcha_token,
        image_data_url=challenge.image_data_url,
        expires_in_seconds=challenge.expires_in_seconds,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> LoginResponse:
    if not request.captcha_token or not request.captcha_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码错误或已过期",
        )
    if not verify_captcha(request.captcha_token, request.captcha_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码错误或已过期",
        )

    user = await authenticate_user(session, request.username, request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        subject=str(user.id),
        role=user.role,
        additional_claims={"username": user.username},
    )
    return LoginResponse(
        access_token=token,
        user_id=str(user.id),
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )

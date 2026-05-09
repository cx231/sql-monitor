from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.auth import LoginRequest, LoginResponse
from app.security import create_access_token
from app.services.auth_service import authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> LoginResponse:
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

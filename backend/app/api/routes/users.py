from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_roles
from app.db.models import User
from app.schemas.users import UserCreate, UserOut, UserPasswordReset, UserUpdate
from app.services.user_service import (
    create_user,
    disable_user,
    list_users,
    reset_user_password,
    update_user,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
async def list_users_route(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles(["admin"])),
) -> list[UserOut]:
    return await list_users(session)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user_route(
    payload: UserCreate,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles(["admin"])),
) -> UserOut:
    try:
        return await create_user(
            session,
            username=payload.username,
            password=payload.password,
            display_name=payload.display_name,
            role=payload.role,
        )
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在",
        )


@router.put("/{user_id}", response_model=UserOut)
async def update_user_route(
    user_id: uuid.UUID,
    payload: UserUpdate,
    session: AsyncSession = Depends(get_db_session),
    current: User = Depends(require_roles(["admin"])),
) -> UserOut:
    if user_id == current.id and payload.status == "disabled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能禁用当前登录用户",
        )

    user = await update_user(
        session,
        user_id,
        display_name=payload.display_name,
        role=payload.role,
        status=payload.status,
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return user


@router.post("/{user_id}/disable", response_model=UserOut)
async def disable_user_route(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current: User = Depends(require_roles(["admin"])),
) -> UserOut:
    if user_id == current.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能禁用当前登录用户",
        )

    user = await disable_user(session, user_id, operator_user_id=current.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return user


@router.post("/{user_id}/reset-password", response_model=UserOut)
async def reset_user_password_route(
    user_id: uuid.UUID,
    payload: UserPasswordReset,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles(["admin"])),
) -> UserOut:
    user = await reset_user_password(session, user_id, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return user

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.security import hash_password


async def list_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).order_by(User.username))
    return list(result.scalars().all())


async def create_user(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    display_name: Optional[str],
    role: str,
) -> User:
    user = User(
        id=uuid.uuid4(),
        username=username,
        password_hash=hash_password(password),
        display_name=display_name,
        role=role,
        status="active",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    display_name: Optional[str],
    role: str,
    status: str,
) -> Optional[User]:
    user = await session.get(User, user_id)
    if user is None:
        return None

    user.display_name = display_name
    user.role = role
    user.status = status
    await session.commit()
    await session.refresh(user)
    return user


async def disable_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    operator_user_id: uuid.UUID,
) -> Optional[User]:
    user = await session.get(User, user_id)
    if user is None or user.id == operator_user_id:
        return None

    user.status = "disabled"
    await session.commit()
    await session.refresh(user)
    return user


async def reset_user_password(
    session: AsyncSession,
    user_id: uuid.UUID,
    password: str,
) -> Optional[User]:
    user = await session.get(User, user_id)
    if user is None:
        return None

    user.password_hash = hash_password(password)
    await session.commit()
    await session.refresh(user)
    return user

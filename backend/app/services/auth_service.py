from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.security import verify_password


async def authenticate_user(
    session: AsyncSession,
    username: str,
    password: str,
) -> Optional[User]:
    statement = select(User).where(User.username == username)
    user = await session.scalar(statement)
    if user is None or user.status != "active":
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user

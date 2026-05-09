from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Callable, Sequence

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    from app.db.postgres import get_session

    async for session in get_session():
        yield session


async def current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="认证凭据无效",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(str(payload.get("sub")))
    except (TypeError, ValueError):
        raise credentials_error

    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None or user.status != "active":
        raise credentials_error
    return user


def require_roles(roles: Sequence[str]) -> Callable[[User], User]:
    allowed_roles = set(roles)

    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="当前用户无权执行该操作",
            )
        return user

    return dependency

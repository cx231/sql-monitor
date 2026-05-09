from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_db_session
from app.db.models import User
from app.schemas.blocking import BlockingOut
from app.services.blocking_service import get_blocking_chains

router = APIRouter(prefix="/blocking", tags=["blocking"])


@router.get("", response_model=BlockingOut)
async def get_blocking_route(
    instance_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(current_user),
) -> BlockingOut:
    blocking = await get_blocking_chains(session, instance_id)
    if blocking is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="LATEST_FRAME_NOT_FOUND",
        )
    return blocking

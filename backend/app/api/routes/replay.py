from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_db_session
from app.db.models import User
from app.schemas.replay import ReplayFrameOut
from app.services.replay_service import get_replay_frame

router = APIRouter(prefix="/replay", tags=["replay"])


@router.get("", response_model=ReplayFrameOut)
async def get_replay_route(
    instance_id: uuid.UUID,
    requested_time: datetime = Query(alias="time"),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(current_user),
) -> ReplayFrameOut:
    replay = await get_replay_frame(session, instance_id, requested_time)
    if replay is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="REPLAY_FRAME_NOT_FOUND",
        )
    return replay

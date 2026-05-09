from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_db_session
from app.db.models import User
from app.schemas.sessions import SessionListItem, SessionListOut, SessionSortBy, SortOrder
from app.services.session_service import list_sessions

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=SessionListOut)
async def get_sessions_route(
    instance_id: uuid.UUID,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    only_blocked: bool = False,
    only_open_transaction: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=1000),
    sort_by: SessionSortBy = "session_id",
    sort_order: SortOrder = "asc",
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(current_user),
) -> SessionListOut:
    result = await list_sessions(
        session,
        instance_id,
        status=status_filter,
        only_blocked=only_blocked,
        only_open_transaction=only_open_transaction,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="LATEST_FRAME_NOT_FOUND",
        )
    return result


@router.get("/{session_id}", response_model=SessionListItem)
async def get_session_route(
    session_id: int,
    instance_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(current_user),
) -> SessionListItem:
    result = await list_sessions(session, instance_id, page=1, page_size=10_000)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="LATEST_FRAME_NOT_FOUND",
        )

    for item in result.items:
        if item.session_id == session_id:
            return item
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="SESSION_NOT_FOUND",
    )

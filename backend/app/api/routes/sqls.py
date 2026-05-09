from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_db_session
from app.db.models import User
from app.schemas.sqls import SortOrder, SqlListItem, SqlListOut, SqlSortBy
from app.services.sql_service import list_sqls

router = APIRouter(prefix="/sqls", tags=["sqls"])


@router.get("", response_model=SqlListOut)
async def get_sqls_route(
    instance_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=1000),
    sort_by: SqlSortBy = "cpu_time_ms",
    sort_order: SortOrder = "desc",
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(current_user),
) -> SqlListOut:
    result = await list_sqls(
        session,
        instance_id,
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


@router.get("/{sql_hash}", response_model=SqlListItem)
async def get_sql_route(
    sql_hash: str,
    instance_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(current_user),
) -> SqlListItem:
    result = await list_sqls(session, instance_id, page=1, page_size=10_000)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="LATEST_FRAME_NOT_FOUND",
        )

    for item in result.items:
        if item.sql_hash == sql_hash:
            return item
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="SQL_NOT_FOUND",
    )

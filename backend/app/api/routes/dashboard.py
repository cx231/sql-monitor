from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_db_session
from app.db.models import User
from app.schemas.dashboard import DashboardOut
from app.services.dashboard_service import get_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
async def get_dashboard_route(
    instance_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(current_user),
) -> DashboardOut:
    dashboard = await get_dashboard(session, instance_id)
    if dashboard is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="LATEST_FRAME_NOT_FOUND",
        )
    return dashboard

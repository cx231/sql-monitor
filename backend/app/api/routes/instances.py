from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_db_session, require_roles
from app.db.models import User
from app.schemas.instances import InstanceCreate, InstanceOut, InstanceUpdate
from app.services.instance_service import create_instance, list_instances, update_instance

router = APIRouter(prefix="/instances", tags=["instances"])


@router.get("", response_model=list[InstanceOut])
async def get_instances(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(current_user),
) -> list[InstanceOut]:
    return await list_instances(session)


@router.post("", response_model=InstanceOut, status_code=status.HTTP_201_CREATED)
async def post_instance(
    request: InstanceCreate,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles(["admin"])),
) -> InstanceOut:
    return await create_instance(session, request)


@router.put("/{instance_id}", response_model=InstanceOut)
async def put_instance(
    instance_id: uuid.UUID,
    request: InstanceUpdate,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles(["admin"])),
) -> InstanceOut:
    instance = await update_instance(session, instance_id, request)
    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="实例不存在",
        )
    return instance

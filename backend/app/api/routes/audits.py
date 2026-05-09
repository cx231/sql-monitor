from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_roles
from app.db.models import User
from app.schemas.kill import KillAuditOut
from app.services.kill_service import list_kill_audits

router = APIRouter(prefix="/audits", tags=["audits"])


@router.get("/kills", response_model=list[KillAuditOut])
async def get_kill_audits(
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_roles(["dba", "admin"])),
) -> list[KillAuditOut]:
    return await list_kill_audits(session, limit=limit)

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_roles
from app.config import get_settings
from app.db.models import User
from app.schemas.kill import KillRequest, KillResponse
from app.services.kill_service import (
    KillAuditStore,
    NoopKillExecutor,
    audit_rejected_kill_request,
    build_kill_target,
    kill_session,
)

router = APIRouter(prefix="/kill", tags=["kill"])


@router.post("", response_model=KillResponse)
async def post_kill(
    request: KillRequest,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_roles(["dba", "admin"])),
) -> KillResponse:
    audit_store = session if hasattr(session, "write_kill_audit") else KillAuditStore(session)
    target = await build_kill_target(session, request.instance_id, request.session_id)
    if target is None:
        response = await audit_rejected_kill_request(
            instance_id=request.instance_id,
            session_id=request.session_id,
            reason=request.reason,
            operator=user,
            audit_store=audit_store,
            error_message="SESSION_NOT_FOUND",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=response.error_message,
        )

    settings = get_settings()
    return await kill_session(
        target=target,
        reason=request.reason,
        operator=user,
        executor=NoopKillExecutor(),
        audit_store=audit_store,
        min_killable_session_id=settings.min_killable_session_id,
    )

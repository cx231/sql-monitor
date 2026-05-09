from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Optional, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KillAudit
from app.schemas.kill import KillResponse
from app.services.dashboard_service import SnapshotRepository, _get
from app.services.session_service import get_session_detail

MIN_REASON_LENGTH = 10
PLATFORM_LOGIN_NAMES = frozenset({"sqlmon_collect", "sqlmon_kill"})
TERMINAL_STATUS_PARTS = ("KILLED", "ROLLBACK")


@dataclass(frozen=True)
class KillTarget:
    instance_id: uuid.UUID
    session_id: int
    login_name: Optional[str]
    status: Optional[str]
    open_transaction_count: int
    blocking_impact_count: int = 0

    def before_snapshot(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "login_name": self.login_name,
            "status": self.status,
            "open_transaction_count": self.open_transaction_count,
            "blocking_impact_count": self.blocking_impact_count,
        }


class KillRejectedError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class KillExecutor(Protocol):
    async def kill(self, instance_id: uuid.UUID, session_id: int) -> None:
        ...


class NoopKillExecutor:
    async def kill(self, instance_id: uuid.UUID, session_id: int) -> None:
        return None


class KillAuditStore:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def write_kill_audit(
        self,
        *,
        operator_user_id: Optional[uuid.UUID],
        operator_name: str,
        instance_id: uuid.UUID,
        session_id: int,
        reason: str,
        before_snapshot: dict[str, object],
        result: str,
        error_message: Optional[str],
    ) -> KillAudit:
        audit = KillAudit(
            id=uuid.uuid4(),
            operator_user_id=operator_user_id,
            operator_name=operator_name,
            instance_id=instance_id,
            session_id=session_id,
            reason=reason,
            before_snapshot=before_snapshot,
            result=result,
            error_message=error_message,
        )
        self.session.add(audit)
        await self.session.commit()
        await self.session.refresh(audit)
        return audit


def validate_kill_target(
    target: KillTarget,
    reason: str,
    min_killable_session_id: int = 50,
    platform_login_names: frozenset[str] = PLATFORM_LOGIN_NAMES,
) -> None:
    if len(reason.strip()) < MIN_REASON_LENGTH:
        raise KillRejectedError("REASON_TOO_SHORT")
    if target.session_id <= min_killable_session_id:
        raise KillRejectedError("SYSTEM_SESSION")

    login_name = (target.login_name or "").strip().lower()
    if login_name in platform_login_names:
        raise KillRejectedError("PLATFORM_ACCOUNT")

    status = (target.status or "").upper()
    if any(part in status for part in TERMINAL_STATUS_PARTS):
        raise KillRejectedError("SESSION_TERMINATING")


async def build_kill_target(
    session_or_repository: Any,
    instance_id: uuid.UUID,
    session_id: int,
) -> Optional[KillTarget]:
    repository = _repository(session_or_repository)
    frame = await repository.get_latest_frame(instance_id)
    if frame is None:
        return None

    detail = await get_session_detail(repository, instance_id, session_id, frame=frame)
    if detail is None:
        return None

    return KillTarget(
        instance_id=instance_id,
        session_id=detail.session_id,
        login_name=detail.login_name,
        status=detail.status,
        open_transaction_count=detail.open_transaction_count,
        blocking_impact_count=await _blocking_impact_count(repository, frame, session_id),
    )


async def kill_session(
    *,
    target: KillTarget,
    reason: str,
    operator: Any,
    executor: KillExecutor,
    audit_store: Any,
    min_killable_session_id: int = 50,
) -> KillResponse:
    result = "success"
    error_message = None

    try:
        validate_kill_target(
            target,
            reason=reason,
            min_killable_session_id=min_killable_session_id,
        )
        await executor.kill(target.instance_id, target.session_id)
    except KillRejectedError as exc:
        result = "rejected"
        error_message = exc.code
    except Exception as exc:
        result = "failed"
        error_message = str(exc)

    audit = await audit_store.write_kill_audit(
        operator_user_id=getattr(operator, "id", None),
        operator_name=_operator_name(operator),
        instance_id=target.instance_id,
        session_id=target.session_id,
        reason=reason,
        before_snapshot=target.before_snapshot(),
        result=result,
        error_message=error_message,
    )

    return KillResponse(
        audit_id=audit.id,
        instance_id=target.instance_id,
        session_id=target.session_id,
        result=result,
        error_message=error_message,
    )


async def audit_rejected_kill_request(
    *,
    instance_id: uuid.UUID,
    session_id: int,
    reason: str,
    operator: Any,
    audit_store: Any,
    error_message: str,
) -> KillResponse:
    target = KillTarget(
        instance_id=instance_id,
        session_id=session_id,
        login_name=None,
        status=None,
        open_transaction_count=0,
        blocking_impact_count=0,
    )
    audit = await audit_store.write_kill_audit(
        operator_user_id=getattr(operator, "id", None),
        operator_name=_operator_name(operator),
        instance_id=instance_id,
        session_id=session_id,
        reason=reason,
        before_snapshot=target.before_snapshot(),
        result="rejected",
        error_message=error_message,
    )
    return KillResponse(
        audit_id=audit.id,
        instance_id=instance_id,
        session_id=session_id,
        result="rejected",
        error_message=error_message,
    )


async def list_kill_audits(session: AsyncSession, limit: int = 100) -> list[KillAudit]:
    result = await session.execute(
        select(KillAudit).order_by(KillAudit.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


def _repository(session_or_repository: Any):
    if hasattr(session_or_repository, "execute"):
        return SnapshotRepository(session_or_repository)
    return session_or_repository


async def _blocking_impact_count(repository: Any, frame: Any, session_id: int) -> int:
    method = getattr(repository, "list_blocking_rows", None)
    if method is None:
        rows = getattr(frame, "blocking_rows", [])
    else:
        rows = await method(frame)
    return len([row for row in rows if _get(row, "blocking_session_id") == session_id])


def _operator_name(operator: Any) -> str:
    return (
        getattr(operator, "username", None)
        or getattr(operator, "display_name", None)
        or str(getattr(operator, "id", "unknown"))
    )

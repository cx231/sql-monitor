from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BlockingSnapshot, RequestSnapshot, SessionSnapshot, SnapshotFrame, SqlText, WaitSnapshot
from app.schemas.dashboard import DashboardMetrics, DashboardOut, TopSql, TopWait


class SnapshotRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_latest_frame(self, instance_id: uuid.UUID):
        result = await self.session.execute(
            select(SnapshotFrame)
            .where(SnapshotFrame.instance_id == instance_id)
            .order_by(SnapshotFrame.snapshot_time.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def get_frame_before(
        self,
        instance_id: uuid.UUID,
        target_time: datetime,
        max_delay_seconds: int,
    ):
        result = await self.session.execute(
            select(SnapshotFrame)
            .where(
                SnapshotFrame.instance_id == instance_id,
                SnapshotFrame.snapshot_time <= target_time,
                SnapshotFrame.snapshot_time >= target_time - timedelta(seconds=max_delay_seconds),
            )
            .order_by(SnapshotFrame.snapshot_time.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def list_sessions(self, frame):
        result = await self.session.execute(
            select(SessionSnapshot)
            .where(
                SessionSnapshot.instance_id == frame.instance_id,
                SessionSnapshot.frame_id == frame.frame_id,
                SessionSnapshot.snapshot_time == frame.snapshot_time,
            )
            .order_by(SessionSnapshot.session_id.asc())
        )
        return list(result.scalars().all())

    async def list_requests(self, frame):
        result = await self.session.execute(
            select(RequestSnapshot)
            .where(
                RequestSnapshot.instance_id == frame.instance_id,
                RequestSnapshot.frame_id == frame.frame_id,
                RequestSnapshot.snapshot_time == frame.snapshot_time,
            )
            .order_by(RequestSnapshot.session_id.asc(), RequestSnapshot.request_id.asc())
        )
        return list(result.scalars().all())

    async def list_waits(self, frame):
        result = await self.session.execute(
            select(WaitSnapshot)
            .where(
                WaitSnapshot.instance_id == frame.instance_id,
                WaitSnapshot.frame_id == frame.frame_id,
                WaitSnapshot.snapshot_time == frame.snapshot_time,
            )
            .order_by(WaitSnapshot.total_wait_time_ms.desc())
        )
        return list(result.scalars().all())

    async def list_blocking_rows(self, frame):
        result = await self.session.execute(
            select(BlockingSnapshot)
            .where(
                BlockingSnapshot.instance_id == frame.instance_id,
                BlockingSnapshot.frame_id == frame.frame_id,
                BlockingSnapshot.snapshot_time == frame.snapshot_time,
            )
            .order_by(BlockingSnapshot.root_session_id.asc(), BlockingSnapshot.chain_depth.asc())
        )
        return list(result.scalars().all())

    async def get_sql_preview_map(self, sql_hashes: Iterable[str]):
        hashes = [value for value in set(sql_hashes) if value]
        if not hashes:
            return {}
        result = await self.session.execute(select(SqlText).where(SqlText.sql_hash.in_(hashes)))
        return {row.sql_hash: row.sql_preview or row.sql_text for row in result.scalars().all()}


async def get_latest_frame(session_or_repository: Any, instance_id: uuid.UUID):
    repository = _repository(session_or_repository)
    return await repository.get_latest_frame(instance_id)


async def get_dashboard(
    session_or_repository: Any,
    instance_id: uuid.UUID,
    frame: Optional[Any] = None,
    top_limit: int = 5,
) -> Optional[DashboardOut]:
    repository = _repository(session_or_repository)
    frame = frame or await repository.get_latest_frame(instance_id)
    if frame is None:
        return None

    sessions = await _maybe_call(repository, "list_sessions", frame, "sessions")
    requests = await _maybe_call(repository, "list_requests", frame, "requests")
    waits = await _maybe_call(repository, "list_waits", frame, "waits")
    blocking_rows = await _maybe_call(repository, "list_blocking_rows", frame, "blocking_rows")
    preview_map = await _sql_preview_map(repository, requests)

    blocked_session_ids = {
        _get(row, "blocked_session_id")
        for row in blocking_rows
        if _get(row, "blocked_session_id") is not None
    }
    root_session_ids = {
        _get(row, "root_session_id")
        for row in blocking_rows
        if _get(row, "root_session_id") is not None
    }
    max_blocking_duration_ms = max(
        [_coalesce(_get(row, "max_wait_time_ms"), _get(row, "wait_duration_ms"), 0) for row in blocking_rows]
        or [0]
    )
    metrics = DashboardMetrics(
        session_count=len(sessions),
        active_request_count=len(requests),
        blocked_session_count=len(blocked_session_ids),
        root_blocker_count=len(root_session_ids),
        max_blocking_duration_ms=max_blocking_duration_ms,
        waiting_request_count=len([request for request in requests if _get(request, "wait_type")]),
    )

    top_waits = [
        _to_top_wait(wait)
        for wait in sorted(waits, key=lambda wait: _coalesce(_get(wait, "total_wait_time_ms"), 0), reverse=True)[
            :top_limit
        ]
    ]
    top_cpu_sqls = [
        _to_top_sql(request, preview_map)
        for request in sorted(
            requests,
            key=lambda request: _coalesce(_get(request, "cpu_time_ms"), 0),
            reverse=True,
        )[:top_limit]
    ]
    top_io_sqls = [
        _to_top_sql(request, preview_map)
        for request in sorted(
            requests,
            key=lambda request: _coalesce(_get(request, "logical_reads"), _get(request, "reads"), 0),
            reverse=True,
        )[:top_limit]
    ]

    return DashboardOut(
        instance_id=instance_id,
        frame_id=_frame_id(frame),
        snapshot_time=frame.snapshot_time,
        collect_delay_seconds=_collect_delay_seconds(frame.snapshot_time),
        metrics=metrics,
        top_waits=top_waits,
        top_cpu_sqls=top_cpu_sqls,
        top_io_sqls=top_io_sqls,
    )


def _repository(session_or_repository: Any):
    if hasattr(session_or_repository, "execute"):
        return SnapshotRepository(session_or_repository)
    return session_or_repository


async def _maybe_call(repository: Any, method_name: str, frame: Any, attribute_name: str):
    method = getattr(repository, method_name, None)
    if method is not None:
        return list(await method(frame))
    return list(getattr(frame, attribute_name, []))


async def _sql_preview_map(repository: Any, requests: list[Any]) -> dict[str, str]:
    sql_hashes = [_get(request, "sql_hash") for request in requests if _get(request, "sql_hash")]
    method = getattr(repository, "get_sql_preview_map", None)
    if method is not None:
        return dict(await method(sql_hashes))
    return {
        _get(request, "sql_hash"): _get(request, "sql_preview")
        for request in requests
        if _get(request, "sql_hash") and _get(request, "sql_preview")
    }


def _to_top_wait(wait: Any) -> TopWait:
    return TopWait(
        wait_type=_get(wait, "wait_type"),
        wait_category=_get(wait, "wait_category"),
        waiting_tasks_count=_coalesce(_get(wait, "waiting_tasks_count"), 0),
        total_wait_time_ms=_coalesce(_get(wait, "total_wait_time_ms"), 0),
        max_wait_time_ms=_coalesce(_get(wait, "max_wait_time_ms"), 0),
    )


def _to_top_sql(request: Any, preview_map: dict[str, str]) -> TopSql:
    sql_hash = _get(request, "sql_hash")
    return TopSql(
        session_id=_get(request, "session_id"),
        request_id=_get(request, "request_id"),
        database_name=_get(request, "database_name"),
        status=_get(request, "status"),
        command=_get(request, "command"),
        duration_ms=_coalesce(_get(request, "duration_ms"), _get(request, "total_elapsed_time_ms")),
        cpu_time_ms=_get(request, "cpu_time_ms"),
        logical_reads=_get(request, "logical_reads"),
        reads=_get(request, "reads"),
        writes=_get(request, "writes"),
        wait_type=_get(request, "wait_type"),
        wait_time_ms=_get(request, "wait_time_ms"),
        blocking_session_id=_get(request, "blocking_session_id"),
        sql_hash=sql_hash,
        normalized_sql_hash=_get(request, "normalized_sql_hash"),
        sql_preview=preview_map.get(sql_hash),
    )


def _collect_delay_seconds(snapshot_time: datetime) -> int:
    now = datetime.now(snapshot_time.tzinfo or timezone.utc)
    return max(int((now - snapshot_time).total_seconds()), 0)


def _frame_id(frame: Any) -> uuid.UUID:
    return _get(frame, "frame_id") or _get(frame, "id")


def _get(row: Any, name: str):
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)


def _coalesce(*values):
    for value in values:
        if value is not None:
            return value
    return None

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BlockingSnapshot, RequestSnapshot, SessionSnapshot, SnapshotFrame, SqlText, WaitSnapshot
from app.schemas.dashboard import DashboardMetrics, DashboardOut, ResourceTrendPoint, TopSql, TopWait


@dataclass(frozen=True)
class FrameRef:
    frame_id: uuid.UUID
    instance_id: uuid.UUID
    snapshot_time: datetime
    collect_duration_ms: int = 0
    status: Optional[str] = None
    cpu_load_percent: Optional[float] = None
    memory_usage_percent: Optional[float] = None
    network_bytes_total: Optional[int] = None
    source: Any = None


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
        return frame_ref(result.scalars().first())

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
        return frame_ref(result.scalars().first())

    async def list_sessions(self, frame):
        ref = frame_ref(frame)
        result = await self.session.execute(
            select(SessionSnapshot)
            .where(
                SessionSnapshot.instance_id == ref.instance_id,
                SessionSnapshot.frame_id == ref.frame_id,
                SessionSnapshot.snapshot_time == ref.snapshot_time,
            )
            .order_by(SessionSnapshot.session_id.asc())
        )
        return list(result.scalars().all())

    async def get_session(self, frame, session_id: int):
        ref = frame_ref(frame)
        result = await self.session.execute(
            select(SessionSnapshot).where(
                SessionSnapshot.instance_id == ref.instance_id,
                SessionSnapshot.frame_id == ref.frame_id,
                SessionSnapshot.snapshot_time == ref.snapshot_time,
                SessionSnapshot.session_id == session_id,
            )
        )
        return result.scalars().first()

    async def list_requests(self, frame):
        ref = frame_ref(frame)
        result = await self.session.execute(
            select(RequestSnapshot)
            .where(
                RequestSnapshot.instance_id == ref.instance_id,
                RequestSnapshot.frame_id == ref.frame_id,
                RequestSnapshot.snapshot_time == ref.snapshot_time,
            )
            .order_by(RequestSnapshot.session_id.asc(), RequestSnapshot.request_id.asc())
        )
        return list(result.scalars().all())

    async def get_request_by_sql_hash(self, frame, sql_hash: str):
        ref = frame_ref(frame)
        result = await self.session.execute(
            select(RequestSnapshot).where(
                RequestSnapshot.instance_id == ref.instance_id,
                RequestSnapshot.frame_id == ref.frame_id,
                RequestSnapshot.snapshot_time == ref.snapshot_time,
                RequestSnapshot.sql_hash == sql_hash,
            )
        )
        return result.scalars().first()

    async def get_request_by_session(self, frame, session_id: int):
        ref = frame_ref(frame)
        result = await self.session.execute(
            select(RequestSnapshot)
            .where(
                RequestSnapshot.instance_id == ref.instance_id,
                RequestSnapshot.frame_id == ref.frame_id,
                RequestSnapshot.snapshot_time == ref.snapshot_time,
                RequestSnapshot.session_id == session_id,
            )
            .order_by(RequestSnapshot.request_id.asc())
        )
        return result.scalars().first()

    async def list_waits(self, frame):
        ref = frame_ref(frame)
        result = await self.session.execute(
            select(WaitSnapshot)
            .where(
                WaitSnapshot.instance_id == ref.instance_id,
                WaitSnapshot.frame_id == ref.frame_id,
                WaitSnapshot.snapshot_time == ref.snapshot_time,
            )
            .order_by(WaitSnapshot.total_wait_time_ms.desc())
        )
        return list(result.scalars().all())

    async def list_blocking_rows(self, frame):
        ref = frame_ref(frame)
        result = await self.session.execute(
            select(BlockingSnapshot)
            .where(
                BlockingSnapshot.instance_id == ref.instance_id,
                BlockingSnapshot.frame_id == ref.frame_id,
                BlockingSnapshot.snapshot_time == ref.snapshot_time,
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

    async def get_sql_text_map(self, sql_hashes: Iterable[str]):
        hashes = [value for value in set(sql_hashes) if value]
        if not hashes:
            return {}
        result = await self.session.execute(select(SqlText).where(SqlText.sql_hash.in_(hashes)))
        return {row.sql_hash: row.sql_text for row in result.scalars().all()}

    async def list_resource_frames(self, instance_id: uuid.UUID, since_time: datetime):
        result = await self.session.execute(
            select(SnapshotFrame)
            .where(
                SnapshotFrame.instance_id == instance_id,
                SnapshotFrame.snapshot_time >= since_time,
            )
            .order_by(SnapshotFrame.snapshot_time.asc())
        )
        return [frame_ref(frame) for frame in result.scalars().all()]

    async def get_resource_frame_before(self, instance_id: uuid.UUID, before_time: datetime):
        result = await self.session.execute(
            select(SnapshotFrame)
            .where(
                SnapshotFrame.instance_id == instance_id,
                SnapshotFrame.snapshot_time < before_time,
            )
            .order_by(SnapshotFrame.snapshot_time.desc())
            .limit(1)
        )
        return frame_ref(result.scalars().first())


async def get_latest_frame(session_or_repository: Any, instance_id: uuid.UUID):
    repository = _repository(session_or_repository)
    return frame_ref(await repository.get_latest_frame(instance_id))


async def get_dashboard(
    session_or_repository: Any,
    instance_id: uuid.UUID,
    frame: Optional[Any] = None,
    top_limit: int = 5,
    metrics_window_minutes: int = 5,
) -> Optional[DashboardOut]:
    repository = _repository(session_or_repository)
    ref = frame_ref(frame or await repository.get_latest_frame(instance_id))
    if ref is None:
        return None

    sessions = await _maybe_call(repository, "list_sessions", ref, "sessions")
    requests = await _maybe_call(repository, "list_requests", ref, "requests")
    waits = await _maybe_call(repository, "list_waits", ref, "waits")
    blocking_rows = await _maybe_call(repository, "list_blocking_rows", ref, "blocking_rows")
    preview_map = await _sql_preview_map(repository, requests)
    sql_text_map = await _sql_text_map(repository, requests)
    resource_trends = await _resource_trends(repository, instance_id, ref, metrics_window_minutes)

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
        _to_top_sql(request, preview_map, sql_text_map)
        for request in sorted(
            requests,
            key=lambda request: _coalesce(_get(request, "cpu_time_ms"), 0),
            reverse=True,
        )[:top_limit]
    ]
    top_io_sqls = [
        _to_top_sql(request, preview_map, sql_text_map)
        for request in sorted(
            requests,
            key=lambda request: _coalesce(_get(request, "logical_reads"), _get(request, "reads"), 0),
            reverse=True,
        )[:top_limit]
    ]

    return DashboardOut(
        instance_id=instance_id,
        frame_id=ref.frame_id,
        snapshot_time=ref.snapshot_time,
        collect_delay_seconds=_collect_delay_seconds(ref.snapshot_time),
        metrics_window_minutes=metrics_window_minutes,
        metrics=metrics,
        resource_trends=resource_trends,
        top_waits=top_waits,
        top_cpu_sqls=top_cpu_sqls,
        top_io_sqls=top_io_sqls,
    )


def _repository(session_or_repository: Any):
    if hasattr(session_or_repository, "execute"):
        return SnapshotRepository(session_or_repository)
    return session_or_repository


def frame_ref(frame: Optional[Any]) -> Optional[FrameRef]:
    if frame is None:
        return None
    if isinstance(frame, FrameRef):
        return frame
    return FrameRef(
        frame_id=_get(frame, "frame_id") or _get(frame, "id"),
        instance_id=_get(frame, "instance_id"),
        snapshot_time=_get(frame, "snapshot_time"),
        collect_duration_ms=_get(frame, "collect_duration_ms") or 0,
        status=_get(frame, "status"),
        cpu_load_percent=_float_or_none(_get(frame, "cpu_load_percent")),
        memory_usage_percent=_float_or_none(_get(frame, "memory_usage_percent")),
        network_bytes_total=_get(frame, "network_bytes_total"),
        source=frame,
    )


async def _maybe_call(repository: Any, method_name: str, frame: Any, attribute_name: str):
    method = getattr(repository, method_name, None)
    if method is not None:
        return list(await method(frame))
    return list(_frame_attribute(frame, attribute_name))


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


async def _sql_text_map(repository: Any, requests: list[Any]) -> dict[str, str]:
    sql_hashes = [_get(request, "sql_hash") for request in requests if _get(request, "sql_hash")]
    method = getattr(repository, "get_sql_text_map", None)
    if method is not None:
        return dict(await method(sql_hashes))
    return {
        _get(request, "sql_hash"): _get(request, "sql_text")
        for request in requests
        if _get(request, "sql_hash") and _get(request, "sql_text")
    }


async def _resource_trends(
    repository: Any,
    instance_id: uuid.UUID,
    ref: FrameRef,
    metrics_window_minutes: int,
) -> list[ResourceTrendPoint]:
    window_minutes = max(metrics_window_minutes, 1)
    since_time = ref.snapshot_time - timedelta(minutes=window_minutes)
    method = getattr(repository, "list_resource_frames", None)
    if method is not None:
        frames = [frame_ref(frame) for frame in await method(instance_id, since_time)]
    else:
        frames = [
            frame_ref(frame)
            for frame in _frame_attribute(ref, "resource_frames")
            if _get(frame, "snapshot_time") and _get(frame, "snapshot_time") >= since_time
        ]
    frames = [frame for frame in frames if frame is not None]
    frames.sort(key=lambda frame: frame.snapshot_time)

    points: list[ResourceTrendPoint] = []
    previous_frame = await _resource_previous_frame(repository, instance_id, since_time)
    for trend_frame in frames:
        points.append(
            ResourceTrendPoint(
                snapshot_time=trend_frame.snapshot_time,
                cpu_load_percent=_float_or_none(_get(trend_frame, "cpu_load_percent")),
                memory_usage_percent=_float_or_none(_get(trend_frame, "memory_usage_percent")),
                network_rate_bytes_per_sec=_network_rate(previous_frame, trend_frame),
            )
        )
        previous_frame = trend_frame
    return points


async def _resource_previous_frame(
    repository: Any,
    instance_id: uuid.UUID,
    before_time: datetime,
) -> Optional[FrameRef]:
    method = getattr(repository, "get_resource_frame_before", None)
    if method is None:
        return None
    return frame_ref(await method(instance_id, before_time))


def _to_top_wait(wait: Any) -> TopWait:
    return TopWait(
        wait_type=_get(wait, "wait_type"),
        wait_category=_get(wait, "wait_category"),
        waiting_tasks_count=_coalesce(_get(wait, "waiting_tasks_count"), 0),
        total_wait_time_ms=_coalesce(_get(wait, "total_wait_time_ms"), 0),
        max_wait_time_ms=_coalesce(_get(wait, "max_wait_time_ms"), 0),
    )


def _to_top_sql(request: Any, preview_map: dict[str, str], sql_text_map: Optional[dict[str, str]] = None) -> TopSql:
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
        sql_text=(sql_text_map or {}).get(sql_hash) or _get(request, "sql_text"),
    )


def _collect_delay_seconds(snapshot_time: datetime) -> int:
    now = datetime.now(snapshot_time.tzinfo or timezone.utc)
    return max(int((now - snapshot_time).total_seconds()), 0)


def _get(row: Any, name: str):
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)


def _float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _network_rate(previous_frame: Optional[FrameRef], current_frame: FrameRef) -> Optional[float]:
    if previous_frame is None:
        return None
    previous_bytes = _get(previous_frame, "network_bytes_total")
    current_bytes = _get(current_frame, "network_bytes_total")
    if previous_bytes is None or current_bytes is None:
        return None
    elapsed_seconds = (current_frame.snapshot_time - previous_frame.snapshot_time).total_seconds()
    if elapsed_seconds <= 0:
        return None
    delta = current_bytes - previous_bytes
    if delta < 0:
        return 0.0
    return delta / elapsed_seconds


def _frame_attribute(frame: Any, name: str):
    value = getattr(frame, name, None)
    if value is not None:
        return value
    source = getattr(frame, "source", None)
    if source is None:
        return []
    return getattr(source, name, [])


def _coalesce(*values):
    for value in values:
        if value is not None:
            return value
    return None

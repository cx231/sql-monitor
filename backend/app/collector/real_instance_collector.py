from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collector.blocking_graph import BlockingInput, build_blocking_edges
from app.collector.collectors.resource_collector import RESOURCE_SQL
from app.collector.collectors.session_request_collector import SESSION_REQUEST_SQL
from app.collector.collectors.wait_collector import WAIT_SQL, categorize_wait
from app.collector.sql_text import normalized_sql_hash, preview_sql, sql_hash
from app.collector.sqlserver_client import SqlServerClient
from app.config import get_settings
from app.db.models import (
    BlockingSnapshot,
    Instance,
    InstanceCollectStatus,
    RequestSnapshot,
    SessionSnapshot,
    SnapshotFrame,
    SqlText,
    WaitSnapshot,
)
from app.services.instance_service import decrypt_connection_string


@dataclass(frozen=True)
class CollectInstanceResult:
    success: bool
    instance_id: uuid.UUID
    frame_id: uuid.UUID | None = None
    sessions_collected: int = 0
    requests_collected: int = 0
    waits_collected: int = 0
    blocking_edges_collected: int = 0
    error_message: str | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def collect_instance_snapshot(
    session: AsyncSession,
    instance: Instance,
    *,
    collect_status: InstanceCollectStatus | None = None,
    client_factory: Callable[[str], Any] = SqlServerClient,
    now: Callable[[], datetime] = utc_now,
) -> CollectInstanceResult:
    instance_id = instance.id
    snapshot_time = now()
    started_at = snapshot_time
    collect_status = collect_status or await _get_or_create_collect_status(session, instance_id)
    consecutive_failures = collect_status.consecutive_failures or 0

    try:
        frame_id = uuid.uuid4()
        connection_string = decrypt_connection_string(instance.encrypted_collect_dsn)
        client = client_factory(connection_string)
        settings = get_settings()
        session_request_rows = client.query(
            SESSION_REQUEST_SQL,
            timeout_seconds=settings.collect_query_timeout_seconds,
        )
        wait_rows = client.query(
            WAIT_SQL,
            timeout_seconds=settings.collect_query_timeout_seconds,
        )
        resource_metrics, resource_available = _collect_resource_metrics(
            client,
            timeout_seconds=settings.collect_query_timeout_seconds,
        )

        session_snapshots, request_snapshots, sql_texts = _build_session_and_request_snapshots(
            frame_id=frame_id,
            instance_id=instance_id,
            snapshot_time=snapshot_time,
            rows=session_request_rows,
        )
        wait_snapshots = _build_wait_snapshots(
            frame_id=frame_id,
            instance_id=instance_id,
            snapshot_time=snapshot_time,
            rows=wait_rows,
        )
        blocking_snapshots = _build_blocking_snapshots(
            frame_id=frame_id,
            instance_id=instance_id,
            snapshot_time=snapshot_time,
            rows=session_request_rows,
            wait_rows=wait_rows,
        )
        duration_ms = _duration_ms(started_at, now())
        await _ensure_snapshot_partitions(session, snapshot_time)
        await _persist_sql_texts(session, sql_texts)
        session.add(
            SnapshotFrame(
                id=frame_id,
                instance_id=instance_id,
                snapshot_time=snapshot_time,
                collect_duration_ms=duration_ms,
                status="success",
                cpu_load_percent=resource_metrics["cpu_load_percent"],
                memory_usage_percent=resource_metrics["memory_usage_percent"],
                network_bytes_total=resource_metrics["network_bytes_total"],
            )
        )
        for obj in [
            *session_snapshots,
            *request_snapshots,
            *wait_snapshots,
            *blocking_snapshots,
        ]:
            session.add(obj)

        instance.status = "online"
        collect_status.status = "success"
        collect_status.last_success_at = snapshot_time
        collect_status.last_duration_ms = duration_ms
        collect_status.consecutive_failures = 0
        collect_status.error_code = None
        collect_status.error_message = None
        collect_status.capabilities = {
            "sessions": True,
            "requests": True,
            "waits": True,
            "blocking": True,
            "resources": resource_available,
        }
        collect_status.updated_at = snapshot_time
        await session.commit()
        return CollectInstanceResult(
            success=True,
            instance_id=instance_id,
            frame_id=frame_id,
            sessions_collected=len(session_snapshots),
            requests_collected=len(request_snapshots),
            waits_collected=len(wait_snapshots),
            blocking_edges_collected=len(blocking_snapshots),
        )
    except Exception:
        await session.rollback()
        await _mark_collect_failed(
            session,
            instance,
            collect_status,
            snapshot_time,
            now,
            consecutive_failures,
        )
        return CollectInstanceResult(
            success=False,
            instance_id=instance_id,
            error_message="采集失败",
        )


async def list_collectable_instances(session: AsyncSession) -> list[tuple[Instance, InstanceCollectStatus]]:
    result = await session.execute(
        select(Instance)
        .where(Instance.status != "disabled")
        .order_by(Instance.created_at.asc())
    )
    instances = list(result.scalars().all())
    pairs = []
    for instance in instances:
        pairs.append((instance, await _get_or_create_collect_status(session, instance.id)))
    return pairs


async def _ensure_snapshot_partitions(session: AsyncSession, snapshot_time: datetime) -> None:
    if not hasattr(session, "execute"):
        return

    month_start = snapshot_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1)
    suffix = month_start.strftime("%Y%m")
    month_start_literal = month_start.isoformat()
    next_month_literal = next_month.isoformat()

    for table_name in (
        "snapshot_frames",
        "session_snapshots",
        "request_snapshots",
        "wait_snapshots",
        "blocking_snapshots",
    ):
        await session.execute(
            text(
                f"CREATE TABLE IF NOT EXISTS {table_name}_{suffix} "
                f"PARTITION OF {table_name} "
                f"FOR VALUES FROM ('{month_start_literal}') TO ('{next_month_literal}')"
            )
        )


async def _persist_sql_texts(session: AsyncSession, sql_texts: list[SqlText]) -> None:
    if not sql_texts:
        return
    if not hasattr(session, "execute"):
        for sql_text in sql_texts:
            session.add(sql_text)
        return

    values = [
        {
            "sql_hash": sql_text.sql_hash,
            "normalized_sql_hash": sql_text.normalized_sql_hash,
            "sql_text": sql_text.sql_text,
            "sql_preview": sql_text.sql_preview,
            "first_seen_at": sql_text.first_seen_at,
            "last_seen_at": sql_text.last_seen_at,
        }
        for sql_text in sql_texts
    ]
    statement = pg_insert(SqlText).values(values)
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[SqlText.sql_hash],
            set_={
                "normalized_sql_hash": statement.excluded.normalized_sql_hash,
                "sql_text": statement.excluded.sql_text,
                "sql_preview": statement.excluded.sql_preview,
                "last_seen_at": statement.excluded.last_seen_at,
            },
        )
    )


async def _get_or_create_collect_status(
    session: AsyncSession,
    instance_id: uuid.UUID,
) -> InstanceCollectStatus:
    collect_status = await session.get(InstanceCollectStatus, instance_id)
    if collect_status is not None:
        return collect_status
    collect_status = InstanceCollectStatus(
        instance_id=instance_id,
        consecutive_failures=0,
        status="unknown",
        capabilities={},
    )
    session.add(collect_status)
    return collect_status


def _build_session_and_request_snapshots(
    *,
    frame_id: uuid.UUID,
    instance_id: uuid.UUID,
    snapshot_time: datetime,
    rows: list[dict[str, Any]],
) -> tuple[list[SessionSnapshot], list[RequestSnapshot], list[SqlText]]:
    sessions: list[SessionSnapshot] = []
    requests: list[RequestSnapshot] = []
    sql_texts: dict[str, SqlText] = {}

    for row in rows:
        row_sql_text = _get(row, "sql_text")
        row_sql_hash = sql_hash(row_sql_text) if row_sql_text else None
        if row_sql_text and row_sql_hash:
            row_normalized_hash = normalized_sql_hash(row_sql_text)
            sql_texts[row_sql_hash] = SqlText(
                sql_hash=row_sql_hash,
                normalized_sql_hash=row_normalized_hash,
                sql_text=row_sql_text,
                sql_preview=preview_sql(row_sql_text, max_length=512),
                first_seen_at=snapshot_time,
                last_seen_at=snapshot_time,
            )
        else:
            row_normalized_hash = None

        sessions.append(
            SessionSnapshot(
                id=uuid.uuid4(),
                frame_id=frame_id,
                instance_id=instance_id,
                snapshot_time=snapshot_time,
                session_id=_get(row, "session_id"),
                login_name=_get(row, "login_name"),
                host_name=_get(row, "host_name"),
                program_name=_get(row, "program_name"),
                database_name=_get(row, "database_name"),
                status=_get(row, "session_status"),
                open_transaction_count=_get(row, "open_transaction_count") or 0,
                login_time=_get(row, "login_time"),
                last_request_start_time=_get(row, "last_request_start_time"),
                last_request_end_time=_get(row, "last_request_end_time"),
                cpu_time=_get(row, "session_cpu_time"),
                reads=_get(row, "session_reads"),
                writes=_get(row, "session_writes"),
                logical_reads=_get(row, "session_logical_reads"),
                current_sql_hash=row_sql_hash,
            )
        )

        if _get(row, "request_id") is None:
            continue

        requests.append(
            RequestSnapshot(
                id=uuid.uuid4(),
                frame_id=frame_id,
                instance_id=instance_id,
                snapshot_time=snapshot_time,
                session_id=_get(row, "session_id"),
                request_id=_get(row, "request_id"),
                database_name=_get(row, "database_name"),
                status=_get(row, "request_status"),
                command=_get(row, "command"),
                start_time=_get(row, "start_time"),
                duration_ms=_get(row, "total_elapsed_time_ms"),
                cpu_time_ms=_get(row, "request_cpu_time_ms"),
                total_elapsed_time_ms=_get(row, "total_elapsed_time_ms"),
                reads=_get(row, "request_reads"),
                writes=_get(row, "request_writes"),
                logical_reads=_get(row, "request_logical_reads"),
                row_count=_get(row, "row_count"),
                wait_type=_get(row, "wait_type"),
                wait_time_ms=_get(row, "wait_time_ms"),
                blocking_session_id=_normalize_blocker(_get(row, "blocking_session_id")),
                percent_complete=_get(row, "percent_complete"),
                sql_hash=row_sql_hash,
                normalized_sql_hash=row_normalized_hash,
                plan_handle=_get(row, "plan_handle"),
                statement_start_offset=_get(row, "statement_start_offset"),
                statement_end_offset=_get(row, "statement_end_offset"),
            )
        )

    return sessions, requests, list(sql_texts.values())


def _resource_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    row = rows[0] if rows else {}
    return {
        "cpu_load_percent": _get(row, "cpu_load_percent"),
        "memory_usage_percent": _get(row, "memory_usage_percent"),
        "network_bytes_total": _get(row, "network_bytes_total"),
    }


def _collect_resource_metrics(client: Any, timeout_seconds: int | None) -> tuple[dict[str, Any], bool]:
    try:
        return _resource_metrics(
            client.query(
                RESOURCE_SQL,
                timeout_seconds=timeout_seconds,
            )
        ), True
    except Exception:
        return _resource_metrics([]), False


def _build_wait_snapshots(
    *,
    frame_id: uuid.UUID,
    instance_id: uuid.UUID,
    snapshot_time: datetime,
    rows: list[dict[str, Any]],
) -> list[WaitSnapshot]:
    grouped: dict[str, list[int]] = {}
    for row in rows:
        wait_type = _get(row, "wait_type")
        if not wait_type:
            continue
        grouped.setdefault(wait_type, []).append(_get(row, "wait_duration_ms") or 0)

    return [
        WaitSnapshot(
            id=uuid.uuid4(),
            frame_id=frame_id,
            instance_id=instance_id,
            snapshot_time=snapshot_time,
            wait_type=wait_type,
            wait_category=categorize_wait(wait_type),
            waiting_tasks_count=len(durations),
            total_wait_time_ms=sum(durations),
            max_wait_time_ms=max(durations or [0]),
        )
        for wait_type, durations in grouped.items()
    ]


def _build_blocking_snapshots(
    *,
    frame_id: uuid.UUID,
    instance_id: uuid.UUID,
    snapshot_time: datetime,
    rows: list[dict[str, Any]],
    wait_rows: list[dict[str, Any]],
) -> list[BlockingSnapshot]:
    resource_by_session = {
        _get(row, "session_id"): _get(row, "resource_description")
        for row in wait_rows
        if _get(row, "session_id") is not None
    }
    blocking_inputs = [
        BlockingInput(
            session_id=_get(row, "session_id"),
            blocker_session_id=_normalize_blocker(_get(row, "blocking_session_id")),
            wait_type=_get(row, "wait_type"),
            wait_duration_ms=_get(row, "wait_time_ms"),
            resource_description=resource_by_session.get(_get(row, "session_id")),
        )
        for row in rows
        if _get(row, "session_id") is not None
    ]
    edges = build_blocking_edges(blocking_inputs)
    blocked_count_by_root = Counter(edge.root_session_id for edge in edges)
    return [
        BlockingSnapshot(
            id=uuid.uuid4(),
            frame_id=frame_id,
            instance_id=instance_id,
            snapshot_time=snapshot_time,
            root_session_id=edge.root_session_id,
            blocking_session_id=edge.blocker_session_id,
            blocked_session_id=edge.blocked_session_id,
            chain_depth=edge.chain_depth,
            blocked_count=blocked_count_by_root[edge.root_session_id],
            max_wait_time_ms=edge.wait_duration_ms,
            wait_type=edge.wait_type,
            resource_description=edge.resource_description,
            cycle_detected=edge.cycle_detected,
            special_blocker_code=edge.blocker_session_id if edge.blocker_session_id < 0 else None,
        )
        for edge in edges
    ]


async def _mark_collect_failed(
    session: AsyncSession,
    instance: Instance,
    collect_status: InstanceCollectStatus,
    snapshot_time: datetime,
    now: Callable[[], datetime],
    consecutive_failures: int | None = None,
) -> None:
    instance.status = "collect_error"
    collect_status.status = "failed"
    collect_status.last_failure_at = snapshot_time
    collect_status.last_duration_ms = _duration_ms(snapshot_time, now())
    collect_status.consecutive_failures = (consecutive_failures or 0) + 1
    collect_status.error_code = "COLLECT_FAILED"
    collect_status.error_message = "采集失败"
    collect_status.updated_at = snapshot_time
    await session.commit()


def _duration_ms(started_at: datetime, finished_at: datetime) -> int:
    return max(int((finished_at - started_at).total_seconds() * 1000), 0)


def _normalize_blocker(blocker_session_id: Any) -> int | None:
    if blocker_session_id in (None, 0):
        return None
    return blocker_session_id


def _get(row: dict[str, Any], name: str):
    return row.get(name)

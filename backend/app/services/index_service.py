from __future__ import annotations

import re
import uuid
from asyncio import to_thread
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collector.sqlserver_client import SqlServerClient
from app.db.models import (
    IndexCollectionStatus,
    IndexFragmentationSnapshot,
    Instance,
    MissingIndexAudit,
    MissingIndexSnapshot,
)
from app.schemas.indexes import IndexAuditOut, IndexCreateResponse, IndexFragmentationActionResponse
from app.services.instance_service import decrypt_connection_string

SYSTEM_DATABASES = frozenset({"master", "model", "msdb", "tempdb"})
IDENTIFIER_PATTERN = re.compile(r"^[^.\[\]\x00]+$")
INDEX_COLLECT_PAGE_SIZE = 500
INDEX_CREATE_FAILED = "INDEX_CREATE_FAILED"
INDEX_CREATE_TIMEOUT = "INDEX_CREATE_TIMEOUT"
INDEX_MAINTENANCE_FAILED = "INDEX_MAINTENANCE_FAILED"
INDEX_MAINTENANCE_TIMEOUT = "INDEX_MAINTENANCE_TIMEOUT"

USER_DATABASES_SQL = """
SELECT name AS database_name
FROM sys.databases
WHERE state_desc = 'ONLINE'
  AND database_id > 4
ORDER BY name
"""

MISSING_INDEX_BASE_CTE = """
WITH missing_index_candidates AS (
  SELECT
    DB_NAME(mid.database_id) AS database_name,
    OBJECT_SCHEMA_NAME(mid.object_id, mid.database_id) AS schema_name,
    OBJECT_NAME(mid.object_id, mid.database_id) AS table_name,
    mid.equality_columns,
    mid.inequality_columns,
    mid.included_columns,
    migs.user_seeks,
    migs.user_scans,
    migs.avg_total_user_cost,
    migs.avg_user_impact,
    ROW_NUMBER() OVER (
      ORDER BY migs.avg_total_user_cost * migs.avg_user_impact * (migs.user_seeks + migs.user_scans) DESC
    ) AS row_number
  FROM sys.dm_db_missing_index_details AS mid
  JOIN sys.dm_db_missing_index_groups AS mig
    ON mid.index_handle = mig.index_handle
  JOIN sys.dm_db_missing_index_group_stats AS migs
    ON mig.index_group_handle = migs.group_handle
  WHERE mid.database_id = DB_ID(?)
)
"""

MISSING_INDEX_COUNT_SQL = MISSING_INDEX_BASE_CTE + """
SELECT COUNT_BIG(*) AS total
FROM missing_index_candidates
"""

MISSING_INDEX_SQL = MISSING_INDEX_BASE_CTE + """
SELECT
  database_name,
  schema_name,
  table_name,
  equality_columns,
  inequality_columns,
  included_columns,
  user_seeks,
  user_scans,
  avg_total_user_cost,
  avg_user_impact
FROM missing_index_candidates
WHERE row_number BETWEEN ? AND ?
ORDER BY row_number
"""

FRAGMENTATION_TARGET_COUNT_SQL = """
SELECT COUNT_BIG(*) AS total
FROM {database_name}.sys.indexes AS i
JOIN {database_name}.sys.objects AS o
  ON i.object_id = o.object_id
WHERE i.index_id > 0
  AND i.name IS NOT NULL
  AND i.is_disabled = 0
  AND i.is_hypothetical = 0
  AND o.is_ms_shipped = 0
  AND o.type = 'U'
"""

FRAGMENTATION_SQL = """
WITH index_targets AS (
  SELECT
    DB_NAME(DB_ID(?)) AS database_name,
    s.name AS schema_name,
    o.name AS table_name,
    o.object_id,
    i.index_id,
    i.name AS index_name,
    ROW_NUMBER() OVER (ORDER BY o.name ASC, i.name ASC, i.index_id ASC) AS row_number
  FROM {database_name}.sys.indexes AS i
  JOIN {database_name}.sys.objects AS o
    ON i.object_id = o.object_id
  JOIN {database_name}.sys.schemas AS s
    ON o.schema_id = s.schema_id
  WHERE i.index_id > 0
    AND i.name IS NOT NULL
    AND i.is_disabled = 0
    AND i.is_hypothetical = 0
    AND o.is_ms_shipped = 0
    AND o.type = 'U'
)
SELECT
  target.database_name,
  target.schema_name,
  target.table_name,
  target.object_id,
  target.index_id,
  target.index_name,
  COALESCE(ips.index_type_desc, '') AS index_type,
  COALESCE(ips.partition_number, 1) AS partition_number,
  COALESCE(ips.avg_fragmentation_in_percent, 0) AS avg_fragmentation_in_percent,
  COALESCE(ips.page_count, 0) AS page_count
FROM index_targets AS target
OUTER APPLY sys.dm_db_index_physical_stats(
  DB_ID(?),
  target.object_id,
  target.index_id,
  NULL,
  'LIMITED'
) AS ips
WHERE row_number BETWEEN ? AND ?
  AND (ips.database_id = DB_ID(?) OR ips.database_id IS NULL)
ORDER BY row_number, COALESCE(ips.partition_number, 1)
"""

ONLINE_REBUILD_SUPPORT_SQL = """
SELECT
  CAST(SERVERPROPERTY('EngineEdition') AS int) AS engine_edition,
  CAST(SERVERPROPERTY('Edition') AS nvarchar(128)) AS edition,
  TRY_CONVERT(int, SERVERPROPERTY('ProductMajorVersion')) AS product_major_version
"""


@dataclass(frozen=True)
class MissingIndexCandidate:
    database_name: str
    schema_name: str
    table_name: str
    equality_columns: list[str]
    inequality_columns: list[str]
    include_columns: list[str]
    user_seeks: int
    user_scans: int
    avg_total_user_cost: float
    avg_user_impact: float
    recommended_index_name: str
    create_enabled: bool
    error_message: Optional[str]


@dataclass(frozen=True)
class MissingIndexPage:
    items: list[MissingIndexCandidate]
    total: int


@dataclass(frozen=True)
class IndexFragmentationItem:
    database_name: str
    schema_name: str
    table_name: str
    index_name: str
    index_type: str
    partition_number: int
    avg_fragmentation_in_percent: float
    page_count: int
    recommended_action: str
    action_enabled: bool
    online_rebuild_supported: bool
    error_message: Optional[str]


@dataclass(frozen=True)
class IndexFragmentationPage:
    items: list[IndexFragmentationItem]
    total: int


@dataclass(frozen=True)
class IndexSnapshotPage:
    items: list[Any]
    total: int
    checked_at: Optional[datetime]
    collection_status: str
    collection_error: Optional[str]
    stale: bool


@dataclass(frozen=True)
class CreateIndexRequestData:
    instance_id: uuid.UUID
    database_name: str
    schema_name: str
    table_name: str
    key_columns: list[str]
    include_columns: list[str]
    index_name: str


@dataclass(frozen=True)
class FragmentationActionRequestData:
    instance_id: uuid.UUID
    database_name: str
    schema_name: str
    table_name: str
    index_name: str
    partition_number: int
    action: str
    avg_fragmentation_in_percent: float
    page_count: int


MissingIndexStore = MissingIndexAudit


class IndexNameConflictError(ValueError):
    pass


def list_user_databases(client: Any) -> list[str]:
    rows = client.query(USER_DATABASES_SQL, timeout_seconds=10)
    databases: list[str] = []
    for row in rows:
        name = str(row.get("database_name") or "")
        if name and name.lower() not in SYSTEM_DATABASES:
            databases.append(name)
    return databases


def list_missing_indexes(client: Any, database_name: str) -> list[MissingIndexCandidate]:
    items: list[MissingIndexCandidate] = []
    page = 1
    while True:
        result = list_missing_indexes_page(
            client,
            database_name=database_name,
            page=page,
            page_size=INDEX_COLLECT_PAGE_SIZE,
            resolve_name_conflicts=False,
        )
        items.extend(result.items)
        if page * INDEX_COLLECT_PAGE_SIZE >= result.total or not result.items:
            return items
        page += 1


def list_missing_indexes_page(
    client: Any,
    database_name: str,
    page: int,
    page_size: int,
    *,
    resolve_name_conflicts: bool = True,
) -> MissingIndexPage:
    _validate_identifier(database_name, "database_name")
    total_rows = client.query(MISSING_INDEX_COUNT_SQL, parameters=[database_name], timeout_seconds=5)
    total = int((total_rows[0] if total_rows else {}).get("total") or 0)
    start_row = (page - 1) * page_size + 1
    end_row = page * page_size
    rows = client.query(
        MISSING_INDEX_SQL,
        parameters=[database_name, start_row, end_row],
        timeout_seconds=10,
    )
    candidates: list[MissingIndexCandidate] = []
    for row in rows:
        table_name = str(row.get("table_name") or "")
        schema_name = str(row.get("schema_name") or "")
        equality_columns = _parse_column_list(row.get("equality_columns"))
        inequality_columns = _parse_column_list(row.get("inequality_columns"))
        include_columns = _parse_column_list(row.get("included_columns"))
        key_columns = equality_columns + inequality_columns
        if not table_name or not schema_name or not key_columns:
            continue

        recommended_index_name = build_lightweight_index_name(
            table_name=table_name,
            key_columns=key_columns,
        )
        if resolve_name_conflicts:
            recommended_index_name = build_default_index_name(
                client,
                database_name=database_name,
                schema_name=schema_name,
                table_name=table_name,
                key_columns=key_columns,
            )

        candidates.append(
            MissingIndexCandidate(
                database_name=str(row.get("database_name") or database_name),
                schema_name=schema_name,
                table_name=table_name,
                equality_columns=equality_columns,
                inequality_columns=inequality_columns,
                include_columns=include_columns,
                user_seeks=int(row.get("user_seeks") or 0),
                user_scans=int(row.get("user_scans") or 0),
                avg_total_user_cost=float(row.get("avg_total_user_cost") or 0),
                avg_user_impact=float(row.get("avg_user_impact") or 0),
                recommended_index_name=recommended_index_name,
                create_enabled=True,
                error_message=None,
            )
        )
    return MissingIndexPage(items=candidates, total=total)


def list_index_fragmentation(client: Any, database_name: str) -> list[IndexFragmentationItem]:
    items: list[IndexFragmentationItem] = []
    page = 1
    while True:
        result = list_index_fragmentation_page(
            client,
            database_name=database_name,
            page=page,
            page_size=INDEX_COLLECT_PAGE_SIZE,
        )
        items.extend(result.items)
        if page * INDEX_COLLECT_PAGE_SIZE >= result.total or not result.items:
            items.sort(key=lambda item: item.avg_fragmentation_in_percent, reverse=True)
            return items
        page += 1


def list_index_fragmentation_page(
    client: Any,
    database_name: str,
    page: int,
    page_size: int,
) -> IndexFragmentationPage:
    _validate_identifier(database_name, "database_name")
    online_supported = supports_online_index_rebuild(client)
    quoted_database = _quote_identifier(database_name)
    total_rows = client.query(
        FRAGMENTATION_TARGET_COUNT_SQL.format(database_name=quoted_database),
        timeout_seconds=5,
    )
    total = int((total_rows[0] if total_rows else {}).get("total") or 0)
    start_row = (page - 1) * page_size + 1
    end_row = page * page_size
    rows = client.query(
        FRAGMENTATION_SQL.format(database_name=quoted_database),
        parameters=[database_name, database_name, start_row, end_row, database_name],
        timeout_seconds=15,
    )
    items = [_fragmentation_item(row, database_name, online_supported) for row in rows]
    items.sort(key=lambda item: item.avg_fragmentation_in_percent, reverse=True)
    return IndexFragmentationPage(items=items, total=total)


def _fragmentation_item(
    row: dict[str, Any],
    database_name: str,
    online_supported: bool,
) -> IndexFragmentationItem:
    fragmentation = float(row.get("avg_fragmentation_in_percent") or 0)
    page_count = int(row.get("page_count") or 0)
    action = recommend_fragmentation_action(fragmentation, page_count)
    return IndexFragmentationItem(
        database_name=str(row.get("database_name") or database_name),
        schema_name=str(row.get("schema_name") or ""),
        table_name=str(row.get("table_name") or ""),
        index_name=str(row.get("index_name") or ""),
        index_type=str(row.get("index_type") or ""),
        partition_number=int(row.get("partition_number") or 1),
        avg_fragmentation_in_percent=fragmentation,
        page_count=page_count,
        recommended_action=action,
        action_enabled=action in {"REORGANIZE", "REBUILD"},
        online_rebuild_supported=online_supported,
        error_message=None,
    )


def recommend_fragmentation_action(fragmentation_percent: float, page_count: int) -> str:
    if page_count < 1000:
        return "NONE"
    if fragmentation_percent > 30:
        return "REBUILD"
    if fragmentation_percent >= 5:
        return "REORGANIZE"
    return "NONE"


def supports_online_index_rebuild(client: Any) -> bool:
    rows = client.query(ONLINE_REBUILD_SUPPORT_SQL, timeout_seconds=5)
    row = rows[0] if rows else {}
    edition = str(row.get("edition") or "").lower()
    engine_edition = int(row.get("engine_edition") or 0)
    major_version = int(row.get("product_major_version") or 0)
    if engine_edition in {5, 8}:
        return True
    if "enterprise" in edition or "developer" in edition:
        return True
    return major_version >= 15


async def _get_index_status(
    session: AsyncSession,
    instance_id: uuid.UUID,
    database_name: str,
    index_type: str,
) -> IndexCollectionStatus | None:
    return await session.get(
        IndexCollectionStatus,
        {
            "instance_id": instance_id,
            "database_name": database_name,
            "index_type": index_type,
        },
    )


def _latest_collected_at(snapshots: list[Any]) -> Optional[datetime]:
    return max(
        (
            snapshot.collected_at
            for snapshot in snapshots
            if getattr(snapshot, "collected_at", None) is not None
        ),
        default=None,
    )


def _snapshot_stale(
    checked_at: Optional[datetime],
    now_value: datetime,
    interval_seconds: int,
) -> bool:
    if checked_at is None:
        return True
    return (now_value - checked_at).total_seconds() > interval_seconds


def _missing_snapshot_item(snapshot: MissingIndexSnapshot) -> MissingIndexCandidate:
    return MissingIndexCandidate(
        database_name=snapshot.database_name,
        schema_name=snapshot.schema_name,
        table_name=snapshot.table_name,
        equality_columns=list(snapshot.equality_columns or []),
        inequality_columns=list(snapshot.inequality_columns or []),
        include_columns=list(snapshot.include_columns or []),
        user_seeks=int(snapshot.user_seeks or 0),
        user_scans=int(snapshot.user_scans or 0),
        avg_total_user_cost=float(snapshot.avg_total_user_cost or 0),
        avg_user_impact=float(snapshot.avg_user_impact or 0),
        recommended_index_name=snapshot.recommended_index_name,
        create_enabled=True,
        error_message=None,
    )


def _fragmentation_snapshot_item(snapshot: IndexFragmentationSnapshot) -> IndexFragmentationItem:
    action = str(snapshot.recommended_action or "NONE")
    return IndexFragmentationItem(
        database_name=snapshot.database_name,
        schema_name=snapshot.schema_name,
        table_name=snapshot.table_name,
        index_name=snapshot.index_name,
        index_type=snapshot.index_type,
        partition_number=int(snapshot.partition_number or 1),
        avg_fragmentation_in_percent=float(snapshot.avg_fragmentation_in_percent or 0),
        page_count=int(snapshot.page_count or 0),
        recommended_action=action,
        action_enabled=action in {"REORGANIZE", "REBUILD"},
        online_rebuild_supported=bool(snapshot.online_rebuild_supported),
        error_message=None,
    )


def build_default_index_name(
    client: Any,
    *,
    database_name: str,
    schema_name: str,
    table_name: str,
    key_columns: list[str],
) -> str:
    base_name = _truncate_identifier(
        "IX_" + "_".join([_name_part(table_name), *[_name_part(column) for column in key_columns]])
    )
    existing_names = _existing_index_names(client, database_name, schema_name, table_name)
    if base_name not in existing_names:
        return base_name

    stem = _truncate_identifier(base_name, reserve=4)
    sequence = 1
    while sequence < 1000:
        candidate = f"{stem}_{sequence:03d}"
        if candidate not in existing_names:
            return candidate
        sequence += 1
    raise RuntimeError("INDEX_NAME_SEQUENCE_EXHAUSTED")


def build_lightweight_index_name(
    *,
    table_name: str,
    key_columns: list[str],
) -> str:
    return _truncate_identifier(
        "IX_" + "_".join([_name_part(table_name), *[_name_part(column) for column in key_columns]])
    )


def build_create_index_sql(
    *,
    database_name: str,
    schema_name: str,
    table_name: str,
    index_name: str,
    key_columns: list[str],
    include_columns: list[str],
) -> str:
    if not key_columns:
        raise ValueError("KEY_COLUMNS_REQUIRED")
    identifiers = [database_name, schema_name, table_name, index_name, *key_columns, *include_columns]
    for identifier in identifiers:
        _validate_identifier(identifier, "identifier")

    sql = (
        f"CREATE INDEX {_quote_identifier(index_name)} "
        f"ON {_quote_identifier(database_name)}.{_quote_identifier(schema_name)}."
        f"{_quote_identifier(table_name)} ({_quote_columns(key_columns)})"
    )
    if include_columns:
        sql += f" INCLUDE ({_quote_columns(include_columns)})"
    return sql


def build_index_maintenance_sql(
    *,
    database_name: str,
    schema_name: str,
    table_name: str,
    index_name: str,
    action: str,
    online_rebuild: bool,
) -> str:
    if action not in {"REORGANIZE", "REBUILD"}:
        raise ValueError("INVALID_FRAGMENTATION_ACTION")
    identifiers = [database_name, schema_name, table_name, index_name]
    for identifier in identifiers:
        _validate_identifier(identifier, "identifier")
    sql = (
        f"ALTER INDEX {_quote_identifier(index_name)} "
        f"ON {_quote_identifier(database_name)}.{_quote_identifier(schema_name)}."
        f"{_quote_identifier(table_name)} {action}"
    )
    if action == "REBUILD" and online_rebuild:
        sql += " WITH (ONLINE = ON)"
    return sql


async def get_user_databases(
    session: AsyncSession,
    instance_id: uuid.UUID,
    client_factory: Callable[[str], Any] = SqlServerClient,
) -> list[str] | None:
    instance = await session.get(Instance, instance_id)
    if instance is None:
        return None
    result = await session.execute(
        select(IndexCollectionStatus.database_name)
        .where(IndexCollectionStatus.instance_id == instance_id)
        .where(IndexCollectionStatus.database_name != "*")
        .order_by(IndexCollectionStatus.database_name.asc())
    )
    databases = {str(database_name) for database_name in result.scalars().all()}
    if not databases:
        try:
            databases.update(
                list_user_databases(client_factory(decrypt_connection_string(instance.encrypted_collect_dsn)))
            )
        except Exception:
            pass
    configured_database = str(instance.database_name or "")
    if configured_database and configured_database.lower() not in SYSTEM_DATABASES:
        databases.add(configured_database)
    return sorted(databases)


async def get_missing_indexes(
    session: AsyncSession,
    instance_id: uuid.UUID,
    database_name: str,
    page: int = 1,
    page_size: int = 20,
    client_factory: Callable[[str], Any] = SqlServerClient,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> IndexSnapshotPage | None:
    instance = await session.get(Instance, instance_id)
    if instance is None:
        return None
    if database_name.lower() in SYSTEM_DATABASES:
        raise ValueError("SYSTEM_DATABASE_NOT_SUPPORTED")
    total = await session.scalar(
        select(func.count())
        .select_from(MissingIndexSnapshot)
        .where(MissingIndexSnapshot.instance_id == instance_id)
        .where(MissingIndexSnapshot.database_name == database_name)
    )
    result = await session.execute(
        select(MissingIndexSnapshot)
        .where(MissingIndexSnapshot.instance_id == instance_id)
        .where(MissingIndexSnapshot.database_name == database_name)
        .order_by(MissingIndexSnapshot.avg_total_user_cost.desc(), MissingIndexSnapshot.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    snapshots = list(result.scalars().all())
    status = await _get_index_status(session, instance_id, database_name, "missing")
    checked_at = status.last_success_at if status else _latest_collected_at(snapshots)
    return IndexSnapshotPage(
        items=[_missing_snapshot_item(snapshot) for snapshot in snapshots],
        total=int(total or 0),
        checked_at=checked_at,
        collection_status=status.status if status else "unknown",
        collection_error=status.error_message if status else None,
        stale=_snapshot_stale(
            checked_at,
            now(),
            instance.missing_index_collect_interval_seconds,
        ),
    )


async def get_index_fragmentation(
    session: AsyncSession,
    instance_id: uuid.UUID,
    database_name: str,
    page: int = 1,
    page_size: int = 20,
    client_factory: Callable[[str], Any] = SqlServerClient,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> IndexSnapshotPage | None:
    instance = await session.get(Instance, instance_id)
    if instance is None:
        return None
    if database_name.lower() in SYSTEM_DATABASES:
        raise ValueError("SYSTEM_DATABASE_NOT_SUPPORTED")
    total = await session.scalar(
        select(func.count())
        .select_from(IndexFragmentationSnapshot)
        .where(IndexFragmentationSnapshot.instance_id == instance_id)
        .where(IndexFragmentationSnapshot.database_name == database_name)
    )
    result = await session.execute(
        select(IndexFragmentationSnapshot)
        .where(IndexFragmentationSnapshot.instance_id == instance_id)
        .where(IndexFragmentationSnapshot.database_name == database_name)
        .order_by(
            IndexFragmentationSnapshot.avg_fragmentation_in_percent.desc(),
            IndexFragmentationSnapshot.id.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    snapshots = list(result.scalars().all())
    status = await _get_index_status(session, instance_id, database_name, "fragmentation")
    checked_at = status.last_success_at if status else _latest_collected_at(snapshots)
    return IndexSnapshotPage(
        items=[_fragmentation_snapshot_item(snapshot) for snapshot in snapshots],
        total=int(total or 0),
        checked_at=checked_at,
        collection_status=status.status if status else "unknown",
        collection_error=status.error_message if status else None,
        stale=_snapshot_stale(
            checked_at,
            now(),
            instance.index_fragmentation_collect_interval_seconds,
        ),
    )


async def create_missing_index(
    session: AsyncSession,
    data: CreateIndexRequestData,
    *,
    operator: Any,
    client_factory: Callable[[str], Any] = SqlServerClient,
) -> IndexCreateResponse:
    instance = await session.get(Instance, data.instance_id)
    if instance is None:
        raise LookupError("INSTANCE_NOT_FOUND")

    client = client_factory(_operation_connection_string(instance))
    existing_names = _existing_index_names(
        client,
        data.database_name,
        data.schema_name,
        data.table_name,
    )
    if data.index_name in existing_names:
        await _write_index_audit(
            session,
            data=data,
            operator=operator,
            ddl_summary="",
            result="rejected",
            error_message="INDEX_NAME_CONFLICT",
        )
        raise IndexNameConflictError("INDEX_NAME_CONFLICT")

    ddl = build_create_index_sql(
        database_name=data.database_name,
        schema_name=data.schema_name,
        table_name=data.table_name,
        index_name=data.index_name,
        key_columns=data.key_columns,
        include_columns=data.include_columns,
    )
    audit = await _write_index_audit(
        session,
        data=data,
        operator=operator,
        ddl_summary=ddl,
        result="running",
        error_message=None,
    )
    return _response(audit, data, result="running", error_message=None)


async def run_missing_index_ddl(
    session: AsyncSession,
    audit_id: uuid.UUID,
    *,
    client_factory: Callable[[str], Any] = SqlServerClient,
) -> None:
    audit = await session.get(MissingIndexStore, audit_id)
    if audit is None:
        return
    instance = await session.get(Instance, audit.instance_id)
    if instance is None:
        await _mark_index_audit_finished(
            session,
            audit,
            result="failed",
            error_message="INSTANCE_NOT_FOUND",
        )
        return

    client = client_factory(_operation_connection_string(instance))
    try:
        await _execute_ddl(client, audit.ddl_summary, timeout_seconds=_index_operation_timeout(instance))
    except Exception as exc:
        await _mark_index_audit_finished(
            session,
            audit,
            result="failed",
            error_message=INDEX_CREATE_TIMEOUT if _is_timeout_error(exc) else INDEX_CREATE_FAILED,
        )
        return

    await _mark_index_audit_finished(
        session,
        audit,
        result="success",
        error_message=None,
    )


async def execute_fragmentation_action(
    session: AsyncSession,
    data: FragmentationActionRequestData,
    *,
    operator: Any,
    client_factory: Callable[[str], Any] = SqlServerClient,
) -> IndexFragmentationActionResponse:
    instance = await session.get(Instance, data.instance_id)
    if instance is None:
        raise LookupError("INSTANCE_NOT_FOUND")
    if data.action not in {"REORGANIZE", "REBUILD"}:
        raise ValueError("INVALID_FRAGMENTATION_ACTION")

    client = client_factory(_operation_connection_string(instance))
    online_used = data.action == "REBUILD" and supports_online_index_rebuild(client)
    ddl = build_index_maintenance_sql(
        database_name=data.database_name,
        schema_name=data.schema_name,
        table_name=data.table_name,
        index_name=data.index_name,
        action=data.action,
        online_rebuild=online_used,
    )
    audit = await _write_fragmentation_audit(
        session,
        data=data,
        operator=operator,
        ddl_summary=ddl,
        online_used=online_used,
        result="running",
        error_message=None,
    )
    return _fragmentation_response(
        audit,
        data,
        online_used=online_used,
        result="running",
        error_message=None,
    )


async def run_fragmentation_ddl(
    session: AsyncSession,
    audit_id: uuid.UUID,
    *,
    client_factory: Callable[[str], Any] = SqlServerClient,
) -> None:
    audit = await session.get(MissingIndexStore, audit_id)
    if audit is None:
        return
    instance = await session.get(Instance, audit.instance_id)
    if instance is None:
        await _mark_index_audit_finished(
            session,
            audit,
            result="failed",
            error_message="INSTANCE_NOT_FOUND",
        )
        return

    client = client_factory(_operation_connection_string(instance))
    try:
        await _execute_ddl(client, audit.ddl_summary, timeout_seconds=_index_operation_timeout(instance))
    except Exception as exc:
        await _mark_index_audit_finished(
            session,
            audit,
            result="failed",
            error_message=(
                INDEX_MAINTENANCE_TIMEOUT if _is_timeout_error(exc) else INDEX_MAINTENANCE_FAILED
            ),
        )
        return

    await _mark_index_audit_finished(
        session,
        audit,
        result="success",
        error_message=None,
    )


async def get_index_audit(session: AsyncSession, audit_id: uuid.UUID) -> IndexAuditOut | None:
    audit = await session.get(MissingIndexStore, audit_id)
    if audit is None:
        return None
    return IndexAuditOut(
        audit_id=audit.id,
        instance_id=audit.instance_id,
        database_name=audit.database_name,
        schema_name=audit.schema_name,
        table_name=audit.table_name,
        index_name=audit.index_name,
        action=audit.action,
        result=audit.result,
        error_message=audit.error_message,
        created_at=audit.created_at,
    )


def _operation_connection_string(instance: Instance) -> str:
    encrypted_dsn = instance.encrypted_kill_dsn or instance.encrypted_collect_dsn
    if not encrypted_dsn:
        raise ValueError("OPERATION_DSN_NOT_CONFIGURED")
    return decrypt_connection_string(encrypted_dsn)


def _index_operation_timeout(instance: Instance) -> int:
    return int(instance.index_operation_timeout_seconds or 1800)


async def _execute_ddl(client: Any, ddl: str, *, timeout_seconds: int) -> None:
    await to_thread(client.execute, ddl, timeout_seconds=timeout_seconds)


async def _mark_index_audit_finished(
    session: AsyncSession,
    audit: MissingIndexAudit,
    *,
    result: str,
    error_message: Optional[str],
) -> None:
    audit.result = result
    audit.error_message = error_message
    await session.commit()
    await session.refresh(audit)


def _is_timeout_error(exc: Exception) -> bool:
    text = " ".join(str(part) for part in getattr(exc, "args", ()) if part)
    if not text:
        text = str(exc)
    normalized = text.lower()
    return any(
        marker in normalized
        for marker in (
            "timeout",
            "timed out",
            "query timeout",
            "login timeout",
            "HYT00".lower(),
            "HYT01".lower(),
            "超时",
        )
    )


async def _write_index_audit(
    session: AsyncSession,
    *,
    data: CreateIndexRequestData,
    operator: Any,
    ddl_summary: str,
    result: str,
    error_message: Optional[str],
) -> MissingIndexAudit:
    audit = MissingIndexStore(
        id=uuid.uuid4(),
        operator_user_id=getattr(operator, "id", None),
        operator_name=getattr(operator, "username", "unknown"),
        instance_id=data.instance_id,
        database_name=data.database_name,
        schema_name=data.schema_name,
        table_name=data.table_name,
        index_name=data.index_name,
        key_columns=data.key_columns,
        include_columns=data.include_columns,
        action="CREATE",
        partition_number=None,
        online_used=None,
        fragmentation_percent=None,
        page_count=None,
        ddl_summary=ddl_summary,
        result=result,
        error_message=error_message,
    )
    session.add(audit)
    await session.commit()
    await session.refresh(audit)
    return audit


async def _write_fragmentation_audit(
    session: AsyncSession,
    *,
    data: FragmentationActionRequestData,
    operator: Any,
    ddl_summary: str,
    online_used: bool,
    result: str,
    error_message: Optional[str],
) -> MissingIndexAudit:
    audit = MissingIndexStore(
        id=uuid.uuid4(),
        operator_user_id=getattr(operator, "id", None),
        operator_name=getattr(operator, "username", "unknown"),
        instance_id=data.instance_id,
        database_name=data.database_name,
        schema_name=data.schema_name,
        table_name=data.table_name,
        index_name=data.index_name,
        key_columns=[],
        include_columns=[],
        action=data.action,
        partition_number=data.partition_number,
        online_used=online_used,
        fragmentation_percent=data.avg_fragmentation_in_percent,
        page_count=data.page_count,
        ddl_summary=ddl_summary,
        result=result,
        error_message=error_message,
    )
    session.add(audit)
    await session.commit()
    await session.refresh(audit)
    return audit


def _fragmentation_response(
    audit: MissingIndexAudit,
    data: FragmentationActionRequestData,
    *,
    online_used: bool,
    result: str,
    error_message: Optional[str],
) -> IndexFragmentationActionResponse:
    return IndexFragmentationActionResponse(
        audit_id=audit.id,
        instance_id=data.instance_id,
        database_name=data.database_name,
        schema_name=data.schema_name,
        table_name=data.table_name,
        index_name=data.index_name,
        partition_number=data.partition_number,
        action=data.action,
        online_used=online_used,
        result=result,
        error_message=error_message,
    )


def _response(
    audit: MissingIndexAudit,
    data: CreateIndexRequestData,
    *,
    result: str,
    error_message: Optional[str],
) -> IndexCreateResponse:
    return IndexCreateResponse(
        audit_id=audit.id,
        instance_id=data.instance_id,
        database_name=data.database_name,
        schema_name=data.schema_name,
        table_name=data.table_name,
        index_name=data.index_name,
        result=result,
        error_message=error_message,
    )


def _existing_index_names(
    client: Any,
    database_name: str,
    schema_name: str,
    table_name: str,
) -> set[str]:
    for value in (database_name, schema_name, table_name):
        _validate_identifier(value, "identifier")
    sql = (
        f"SELECT i.name FROM {_quote_identifier(database_name)}.sys.indexes AS i "
        f"JOIN {_quote_identifier(database_name)}.sys.tables AS t ON i.object_id = t.object_id "
        f"JOIN {_quote_identifier(database_name)}.sys.schemas AS s ON t.schema_id = s.schema_id "
        "WHERE s.name = ? AND t.name = ? AND i.name IS NOT NULL"
    )
    rows = client.query(sql, parameters=[schema_name, table_name], timeout_seconds=10)
    return {str(row.get("name")) for row in rows if row.get("name")}


def _parse_column_list(value: object) -> list[str]:
    if not value:
        return []
    columns: list[str] = []
    for raw in str(value).split(","):
        column = raw.strip()
        if column.startswith("[") and column.endswith("]"):
            column = column[1:-1]
        column = column.strip()
        if column:
            columns.append(column)
    return columns


def _quote_columns(columns: list[str]) -> str:
    return ", ".join(_quote_identifier(column) for column in columns)


def _quote_identifier(value: str) -> str:
    _validate_identifier(value, "identifier")
    return f"[{value.replace(']', ']]')}]"


def _validate_identifier(value: str, field_name: str) -> None:
    if not value or not IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"INVALID_{field_name.upper()}")


def _name_part(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_]+", "_", value).strip("_") or "col"


def _truncate_identifier(value: str, reserve: int = 0) -> str:
    max_length = 128 - reserve
    return value[:max_length]

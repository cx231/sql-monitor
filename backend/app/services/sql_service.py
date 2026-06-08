from __future__ import annotations

import uuid
from typing import Any, Optional

from app.schemas.sqls import SortOrder, SqlListItem, SqlListOut, SqlSortBy
from app.services.dashboard_service import (
    _collect_delay_seconds,
    _frame_attribute,
    _get,
    _repository,
    _sql_preview_map,
    _sql_text_map,
    frame_ref,
)


async def list_sqls(
    session_or_repository: Any,
    instance_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    sort_by: SqlSortBy = "cpu_time_ms",
    sort_order: SortOrder = "desc",
    frame: Optional[Any] = None,
) -> Optional[SqlListOut]:
    repository = _repository(session_or_repository)
    ref = frame_ref(frame or await repository.get_latest_frame(instance_id))
    if ref is None:
        return None

    requests = list(await _load(repository, ref))
    preview_map = await _sql_preview_map(repository, requests)
    sql_text_map = await _sql_text_map(repository, requests)
    reverse = sort_order == "desc"
    requests.sort(key=lambda request: _sort_value(request, sort_by), reverse=reverse)
    total = len(requests)
    start = max(page - 1, 0) * page_size

    return SqlListOut(
        instance_id=instance_id,
        frame_id=ref.frame_id,
        snapshot_time=ref.snapshot_time,
        collect_delay_seconds=_collect_delay_seconds(ref.snapshot_time),
        page=page,
        page_size=page_size,
        total=total,
        items=[
            _to_item(request, preview_map, sql_text_map)
            for request in requests[start : start + page_size]
        ],
    )


async def get_sql_detail(
    session_or_repository: Any,
    instance_id: uuid.UUID,
    sql_hash: str,
    frame: Optional[Any] = None,
) -> Optional[SqlListItem]:
    repository = _repository(session_or_repository)
    ref = frame_ref(frame or await repository.get_latest_frame(instance_id))
    if ref is None:
        return None

    request = await _get_request_by_sql_hash(repository, ref, sql_hash)
    if request is None:
        return None

    preview_map = await _sql_preview_map(repository, [request])
    sql_text_map = await _sql_text_map(repository, [request])
    return _to_item(request, preview_map, sql_text_map)


async def _load(repository: Any, frame: Any):
    method = getattr(repository, "list_requests", None)
    if method is not None:
        return await method(frame)
    return _frame_attribute(frame, "requests")


async def _get_request_by_sql_hash(repository: Any, frame: Any, sql_hash: str):
    method = getattr(repository, "get_request_by_sql_hash", None)
    if method is not None:
        return await method(frame, sql_hash)
    requests = _frame_attribute(frame, "requests")
    return next(
        (request for request in requests if _get(request, "sql_hash") == sql_hash),
        None,
    )


def _to_item(
    request: Any,
    preview_map: dict[str, str],
    sql_text_map: dict[str, str] | None = None,
) -> SqlListItem:
    sql_hash = _get(request, "sql_hash")
    return SqlListItem(
        session_id=_get(request, "session_id"),
        request_id=_get(request, "request_id"),
        database_name=_get(request, "database_name"),
        status=_get(request, "status"),
        command=_get(request, "command"),
        duration_ms=_get(request, "duration_ms") or _get(request, "total_elapsed_time_ms"),
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


def _sort_value(request: Any, sort_by: str):
    value = _get(request, sort_by)
    return -1 if value is None else value

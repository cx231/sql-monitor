from __future__ import annotations

import uuid
from typing import Any, Optional

from app.schemas.sessions import SessionListItem, SessionListOut, SessionSortBy, SortOrder
from app.services.dashboard_service import (
    _collect_delay_seconds,
    _frame_attribute,
    _get,
    _repository,
    _sql_preview_map,
    frame_ref,
)


async def list_sessions(
    session_or_repository: Any,
    instance_id: uuid.UUID,
    status: Optional[str] = None,
    only_blocked: bool = False,
    only_open_transaction: bool = False,
    page: int = 1,
    page_size: int = 50,
    sort_by: SessionSortBy = "session_id",
    sort_order: SortOrder = "asc",
    frame: Optional[Any] = None,
) -> Optional[SessionListOut]:
    repository = _repository(session_or_repository)
    ref = frame_ref(frame or await repository.get_latest_frame(instance_id))
    if ref is None:
        return None

    sessions = list(await _load(repository, ref, "list_sessions", "sessions"))
    requests = list(await _load(repository, ref, "list_requests", "requests"))
    preview_map = await _sql_preview_map(repository, requests)
    request_by_session = {_get(request, "session_id"): request for request in requests}

    filtered = []
    for session in sessions:
        request = request_by_session.get(_get(session, "session_id"))
        if status is not None and _get(session, "status") != status:
            continue
        if only_blocked and (request is None or _get(request, "blocking_session_id") is None):
            continue
        if only_open_transaction and (_get(session, "open_transaction_count") or 0) <= 0:
            continue
        filtered.append((session, request))

    reverse = sort_order == "desc"
    filtered.sort(key=lambda pair: _sort_value(pair[0], sort_by), reverse=reverse)
    total = len(filtered)
    start = max(page - 1, 0) * page_size
    page_items = filtered[start : start + page_size]

    return SessionListOut(
        instance_id=instance_id,
        frame_id=ref.frame_id,
        snapshot_time=ref.snapshot_time,
        collect_delay_seconds=_collect_delay_seconds(ref.snapshot_time),
        page=page,
        page_size=page_size,
        total=total,
        items=[_to_item(session, request, preview_map) for session, request in page_items],
    )


async def get_session_detail(
    session_or_repository: Any,
    instance_id: uuid.UUID,
    session_id: int,
    frame: Optional[Any] = None,
) -> Optional[SessionListItem]:
    repository = _repository(session_or_repository)
    ref = frame_ref(frame or await repository.get_latest_frame(instance_id))
    if ref is None:
        return None

    session = await _get_session(repository, ref, session_id)
    if session is None:
        return None

    request = await _get_request_by_session(repository, ref, session_id)
    preview_map = await _sql_preview_map(repository, [request] if request is not None else [])
    return _to_item(session, request, preview_map)


async def _load(repository: Any, frame: Any, method_name: str, attribute_name: str):
    method = getattr(repository, method_name, None)
    if method is not None:
        return await method(frame)
    return _frame_attribute(frame, attribute_name)


async def _get_session(repository: Any, frame: Any, session_id: int):
    method = getattr(repository, "get_session", None)
    if method is not None:
        return await method(frame, session_id)
    sessions = _frame_attribute(frame, "sessions")
    return next(
        (session for session in sessions if _get(session, "session_id") == session_id),
        None,
    )


async def _get_request_by_session(repository: Any, frame: Any, session_id: int):
    method = getattr(repository, "get_request_by_session", None)
    if method is not None:
        return await method(frame, session_id)
    requests = _frame_attribute(frame, "requests")
    return next(
        (request for request in requests if _get(request, "session_id") == session_id),
        None,
    )


def _to_item(session: Any, request: Optional[Any], preview_map: dict[str, str]) -> SessionListItem:
    current_sql_hash = _get(session, "current_sql_hash")
    request_sql_hash = _get(request, "sql_hash") if request is not None else None
    sql_hash = current_sql_hash or request_sql_hash
    return SessionListItem(
        session_id=_get(session, "session_id"),
        login_name=_get(session, "login_name"),
        host_name=_get(session, "host_name"),
        program_name=_get(session, "program_name"),
        database_name=_get(session, "database_name"),
        status=_get(session, "status"),
        open_transaction_count=_get(session, "open_transaction_count") or 0,
        cpu_time=_get(session, "cpu_time"),
        reads=_get(session, "reads"),
        writes=_get(session, "writes"),
        logical_reads=_get(session, "logical_reads"),
        wait_type=_get(request, "wait_type") if request is not None else None,
        wait_time_ms=_get(request, "wait_time_ms") if request is not None else None,
        blocking_session_id=_get(request, "blocking_session_id") if request is not None else None,
        current_sql_hash=sql_hash,
        current_sql_preview=preview_map.get(sql_hash),
    )


def _sort_value(session: Any, sort_by: str):
    value = _get(session, sort_by)
    return -1 if value is None else value

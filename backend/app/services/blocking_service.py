from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any, Optional

from app.schemas.blocking import BlockingChain, BlockingNode, BlockingOut, RiskLevel
from app.services.dashboard_service import (
    _collect_delay_seconds,
    _frame_attribute,
    _get,
    _repository,
    frame_ref,
)


async def get_blocking_chains(
    session_or_repository: Any,
    instance_id: uuid.UUID,
    frame: Optional[Any] = None,
) -> Optional[BlockingOut]:
    repository = _repository(session_or_repository)
    ref = frame_ref(frame or await repository.get_latest_frame(instance_id))
    if ref is None:
        return None

    rows = list(await _load(repository, ref))
    grouped: dict[object, list[Any]] = defaultdict(list)
    for row in rows:
        grouped[_get(row, "root_session_id")].append(row)

    chains = []
    for root_session_id, group_rows in grouped.items():
        blocked_sessions = {
            _get(row, "blocked_session_id")
            for row in group_rows
            if _get(row, "blocked_session_id") is not None
        }
        blocked_count = max(
            len(blocked_sessions),
            max([_get(row, "blocked_count") or 0 for row in group_rows] or [0]),
        )
        max_wait_time_ms = max(
            [_get(row, "max_wait_time_ms") or _get(row, "wait_duration_ms") or 0 for row in group_rows]
            or [0]
        )
        nodes = [_to_node(row) for row in sorted(group_rows, key=lambda row: _get(row, "chain_depth") or 0)]
        chains.append(
            BlockingChain(
                root_session_id=root_session_id,
                blocked_count=blocked_count,
                max_wait_time_ms=max_wait_time_ms,
                risk_level=_risk_level(blocked_count),
                nodes=nodes,
            )
        )

    chains.sort(key=lambda chain: (chain.blocked_count, chain.max_wait_time_ms), reverse=True)
    return BlockingOut(
        instance_id=instance_id,
        frame_id=ref.frame_id,
        snapshot_time=ref.snapshot_time,
        collect_delay_seconds=_collect_delay_seconds(ref.snapshot_time),
        chains=chains,
    )


async def _load(repository: Any, frame: Any):
    method = getattr(repository, "list_blocking_rows", None)
    if method is not None:
        return await method(frame)
    return _frame_attribute(frame, "blocking_rows")


def _to_node(row: Any) -> BlockingNode:
    return BlockingNode(
        blocking_session_id=_get(row, "blocking_session_id"),
        blocked_session_id=_get(row, "blocked_session_id"),
        chain_depth=_get(row, "chain_depth") or 0,
        wait_type=_get(row, "wait_type"),
        wait_time_ms=_get(row, "max_wait_time_ms") or _get(row, "wait_duration_ms"),
        resource_description=_get(row, "resource_description"),
        cycle_detected=bool(_get(row, "cycle_detected")),
        special_blocker_code=_get(row, "special_blocker_code"),
    )


def _risk_level(blocked_count: int) -> RiskLevel:
    if blocked_count >= 5:
        return "high"
    if blocked_count >= 2:
        return "medium"
    return "low"

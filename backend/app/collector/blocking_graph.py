from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

_SPECIAL_BLOCKERS = {-2, -3, -4}


@dataclass(frozen=True)
class BlockingInput:
    session_id: int
    blocker_session_id: Optional[int]
    wait_type: Optional[str] = None
    wait_duration_ms: Optional[int] = None
    resource_description: Optional[str] = None


@dataclass(frozen=True)
class BlockingEdge:
    root_session_id: int
    blocker_session_id: int
    blocked_session_id: int
    chain_depth: int
    wait_type: Optional[str] = None
    wait_duration_ms: Optional[int] = None
    resource_description: Optional[str] = None
    cycle_detected: bool = False

    @property
    def session_id(self) -> int:
        return self.blocked_session_id


def _normalize_blocker(blocker_session_id: Optional[int]) -> Optional[int]:
    if blocker_session_id in _SPECIAL_BLOCKERS:
        return blocker_session_id
    if blocker_session_id in (None, 0):
        return None
    return blocker_session_id


def build_blocking_edges(rows: Iterable[BlockingInput]) -> List[BlockingEdge]:
    row_map: Dict[int, BlockingInput] = {row.session_id: row for row in rows}
    ordered_rows = list(row_map.values())
    edges: List[BlockingEdge] = []
    seen_edges: Set[Tuple[int, int]] = set()

    def build_chain(session_id: int, path: Set[int]) -> Tuple[int, List[Tuple[int, int, int, bool]]]:
        row = row_map[session_id]
        blocker_session_id = _normalize_blocker(row.blocker_session_id)
        if blocker_session_id is None:
            return session_id, []

        if blocker_session_id in _SPECIAL_BLOCKERS:
            return blocker_session_id, [(blocker_session_id, session_id, 1, False)]

        if blocker_session_id in path:
            return blocker_session_id, [(blocker_session_id, session_id, 1, True)]

        blocker_row = row_map.get(blocker_session_id)
        if blocker_row is None:
            return blocker_session_id, [(blocker_session_id, session_id, 1, False)]

        root_session_id, parent_edges = build_chain(blocker_session_id, path | {session_id})
        chain_depth = len(parent_edges) + 1
        current_edge = (blocker_session_id, session_id, chain_depth, False)
        return root_session_id, parent_edges + [current_edge]

    for row in ordered_rows:
        blocker_session_id = _normalize_blocker(row.blocker_session_id)
        if blocker_session_id is None:
            continue

        root_session_id, chain = build_chain(row.session_id, {row.session_id})
        for blocker_id, blocked_id, chain_depth, cycle_detected in chain:
            edge_key = (blocker_id, blocked_id)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            edges.append(
                BlockingEdge(
                    root_session_id=root_session_id,
                    blocker_session_id=blocker_id,
                    blocked_session_id=blocked_id,
                    chain_depth=chain_depth,
                    wait_type=row_map.get(blocked_id, row).wait_type,
                    wait_duration_ms=row_map.get(blocked_id, row).wait_duration_ms,
                    resource_description=row_map.get(blocked_id, row).resource_description,
                    cycle_detected=cycle_detected,
                )
            )

    return edges

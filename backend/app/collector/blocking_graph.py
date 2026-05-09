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

    def build_chain(session_id: int) -> Tuple[int, List[Tuple[int, int, int, bool]]]:
        current_session_id = session_id
        visited: Set[int] = {session_id}
        child_to_parent_edges: List[Tuple[int, int, bool]] = []

        while True:
            row = row_map[current_session_id]
            blocker_session_id = _normalize_blocker(row.blocker_session_id)
            if blocker_session_id is None:
                root_session_id = current_session_id
                break

            if blocker_session_id in _SPECIAL_BLOCKERS:
                child_to_parent_edges.append((blocker_session_id, current_session_id, False))
                root_session_id = blocker_session_id
                break

            child_to_parent_edges.append((blocker_session_id, current_session_id, False))
            if blocker_session_id in visited:
                root_session_id = blocker_session_id
                child_to_parent_edges[-1] = (blocker_session_id, current_session_id, True)
                break

            blocker_row = row_map.get(blocker_session_id)
            if blocker_row is None:
                root_session_id = blocker_session_id
                break

            visited.add(blocker_session_id)
            current_session_id = blocker_session_id

        chain: List[Tuple[int, int, int, bool]] = []
        for chain_depth, (blocker_id, blocked_id, cycle_detected) in enumerate(
            reversed(child_to_parent_edges),
            start=1,
        ):
            chain.append((blocker_id, blocked_id, chain_depth, cycle_detected))
        return root_session_id, chain

    for row in ordered_rows:
        blocker_session_id = _normalize_blocker(row.blocker_session_id)
        if blocker_session_id is None:
            continue

        root_session_id, chain = build_chain(row.session_id)
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

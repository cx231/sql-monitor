from __future__ import annotations

from app.collector.blocking_graph import BlockingInput, build_blocking_edges


def test_build_blocking_edges_includes_root_blocker_not_present_in_rows() -> None:
    edges = build_blocking_edges(
        [
            BlockingInput(session_id=51, blocker_session_id=50, wait_type="LCK_M_S", wait_duration_ms=100),
        ]
    )

    assert [(edge.blocker_session_id, edge.blocked_session_id) for edge in edges] == [(50, 51)]


def test_build_blocking_edges_follows_chain_depth() -> None:
    edges = build_blocking_edges(
        [
            BlockingInput(session_id=52, blocker_session_id=51, wait_type="LCK_M_S", wait_duration_ms=100),
            BlockingInput(session_id=51, blocker_session_id=50, wait_type="LCK_M_X", wait_duration_ms=200),
        ]
    )

    assert [(edge.blocker_session_id, edge.blocked_session_id) for edge in edges] == [(50, 51), (51, 52)]
    assert [edge.chain_depth for edge in edges] == [1, 2]


def test_build_blocking_edges_handles_long_chain_without_recursion_error() -> None:
    rows = [
        BlockingInput(session_id=session_id, blocker_session_id=session_id - 1)
        for session_id in range(2, 1102)
    ]

    edges = build_blocking_edges(rows)

    assert len(edges) == 1100
    assert edges[0].blocker_session_id == 1
    assert edges[0].blocked_session_id == 2
    assert edges[-1].blocker_session_id == 1100
    assert edges[-1].blocked_session_id == 1101
    assert edges[-1].chain_depth == 1100


def test_build_blocking_edges_handles_special_blockers() -> None:
    edges = build_blocking_edges(
        [
            BlockingInput(session_id=61, blocker_session_id=-2, wait_type="LCK_M_S", wait_duration_ms=100),
            BlockingInput(session_id=62, blocker_session_id=-3, wait_type="LCK_M_S", wait_duration_ms=100),
            BlockingInput(session_id=63, blocker_session_id=-4, wait_type="LCK_M_S", wait_duration_ms=100),
        ]
    )

    assert [(edge.blocker_session_id, edge.blocked_session_id) for edge in edges] == [
        (-2, 61),
        (-3, 62),
        (-4, 63),
    ]


def test_build_blocking_edges_stops_on_cycle() -> None:
    edges = build_blocking_edges(
        [
            BlockingInput(session_id=71, blocker_session_id=72, wait_type="LCK_M_S", wait_duration_ms=100),
            BlockingInput(session_id=72, blocker_session_id=71, wait_type="LCK_M_X", wait_duration_ms=200),
        ]
    )

    assert sorted((edge.blocker_session_id, edge.blocked_session_id) for edge in edges) == [
        (71, 72),
        (72, 71),
    ]
    assert any(edge.cycle_detected for edge in edges)

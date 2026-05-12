from __future__ import annotations

import asyncio

import pytest

from app.collector import main as collector_main


def test_real_collector_reuses_one_event_loop_across_polling_cycles(monkeypatch) -> None:
    loops: list[asyncio.AbstractEventLoop] = []

    class StopCollector(Exception):
        pass

    async def fake_collect_instances_once(instance_id=None) -> None:
        loops.append(asyncio.get_running_loop())
        if len(loops) == 2:
            raise StopCollector

    monkeypatch.setattr(collector_main, "collect_instances_once", fake_collect_instances_once)
    monkeypatch.setattr(collector_main.time, "sleep", lambda seconds: None)

    with pytest.raises(StopCollector):
        collector_main.run_collector(interval_seconds=0)

    assert len(loops) == 2
    assert loops[0] is loops[1]

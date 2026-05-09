from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from app.schemas.replay import ReplayFrameOut
from app.services.blocking_service import get_blocking_chains
from app.services.dashboard_service import _repository, frame_ref, get_dashboard
from app.services.session_service import list_sessions
from app.services.sql_service import list_sqls


async def get_replay_frame(
    session_or_repository: Any,
    instance_id: uuid.UUID,
    requested_time: datetime,
    max_delay_seconds: int = 10,
) -> Optional[ReplayFrameOut]:
    repository = _repository(session_or_repository)
    ref = frame_ref(await repository.get_frame_before(instance_id, requested_time, max_delay_seconds))
    if ref is None:
        return None

    dashboard = await get_dashboard(repository, instance_id, frame=ref)
    sessions = await list_sessions(repository, instance_id, page=1, page_size=10_000, frame=ref)
    sqls = await list_sqls(repository, instance_id, page=1, page_size=10_000, frame=ref)
    blocking = await get_blocking_chains(repository, instance_id, frame=ref)
    if dashboard is None or sessions is None or sqls is None or blocking is None:
        return None

    return ReplayFrameOut(
        instance_id=instance_id,
        requested_time=requested_time,
        snapshot_time=ref.snapshot_time,
        frame_id=ref.frame_id,
        dashboard=dashboard,
        sessions=sessions.items,
        sqls=sqls.items,
        blocking=blocking.chains,
        waits=dashboard.top_waits,
    )

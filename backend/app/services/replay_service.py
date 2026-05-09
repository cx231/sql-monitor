from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from app.schemas.replay import ReplayFrameOut
from app.services.blocking_service import get_blocking_chains
from app.services.dashboard_service import _repository, get_dashboard
from app.services.session_service import list_sessions
from app.services.sql_service import list_sqls


async def get_replay_frame(
    session_or_repository: Any,
    instance_id: uuid.UUID,
    requested_time: datetime,
    max_delay_seconds: int = 10,
) -> Optional[ReplayFrameOut]:
    repository = _repository(session_or_repository)
    frame = await repository.get_frame_before(instance_id, requested_time, max_delay_seconds)
    if frame is None:
        return None

    dashboard = await get_dashboard(repository, instance_id, frame=frame)
    sessions = await list_sessions(repository, instance_id, page=1, page_size=10_000, frame=frame)
    sqls = await list_sqls(repository, instance_id, page=1, page_size=10_000, frame=frame)
    blocking = await get_blocking_chains(repository, instance_id, frame=frame)
    if dashboard is None or sessions is None or sqls is None or blocking is None:
        return None

    return ReplayFrameOut(
        instance_id=instance_id,
        requested_time=requested_time,
        snapshot_time=frame.snapshot_time,
        frame_id=getattr(frame, "frame_id", None) or getattr(frame, "id"),
        dashboard=dashboard,
        sessions=sessions.items,
        sqls=sqls.items,
        blocking=blocking.chains,
        waits=dashboard.top_waits,
    )

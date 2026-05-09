from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.blocking import BlockingChain
from app.schemas.dashboard import DashboardOut, TopWait
from app.schemas.sessions import SessionListItem
from app.schemas.sqls import SqlListItem


class ReplayFrameOut(BaseModel):
    instance_id: uuid.UUID
    requested_time: datetime
    snapshot_time: datetime
    frame_id: uuid.UUID
    dashboard: DashboardOut
    sessions: list[SessionListItem]
    sqls: list[SqlListItem]
    blocking: list[BlockingChain]
    waits: list[TopWait]
    tempdb: list[object] = []

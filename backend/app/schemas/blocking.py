from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

RiskLevel = Literal["low", "medium", "high"]


class BlockingNode(BaseModel):
    blocking_session_id: Optional[int] = None
    blocked_session_id: int
    chain_depth: int
    wait_type: Optional[str] = None
    wait_time_ms: Optional[int] = None
    resource_description: Optional[str] = None
    cycle_detected: bool = False
    special_blocker_code: Optional[int] = None


class BlockingChain(BaseModel):
    root_session_id: Optional[int] = None
    blocked_count: int
    max_wait_time_ms: int
    risk_level: RiskLevel
    nodes: list[BlockingNode]


class BlockingOut(BaseModel):
    instance_id: uuid.UUID
    frame_id: uuid.UUID
    snapshot_time: datetime
    collect_delay_seconds: int
    chains: list[BlockingChain]

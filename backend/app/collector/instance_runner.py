from __future__ import annotations

import uuid
from typing import Optional

from app.collector.mock_data import DEFAULT_MOCK_INSTANCE_ID, MockFrame, build_mock_frame


def collect_instance_once(instance_id: Optional[uuid.UUID] = None) -> MockFrame:
    """采集单个实例的一帧 mock 快照。"""

    return build_mock_frame(instance_id=instance_id or DEFAULT_MOCK_INSTANCE_ID)

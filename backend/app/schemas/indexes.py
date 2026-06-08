from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

IndexCreateResult = Literal["running", "success", "failed", "rejected"]
IndexFragmentationAction = Literal["NONE", "REORGANIZE", "REBUILD"]


class IndexDatabaseListOut(BaseModel):
    instance_id: uuid.UUID
    databases: list[str]


class MissingIndexItem(BaseModel):
    database_name: str
    schema_name: str
    table_name: str
    equality_columns: list[str]
    inequality_columns: list[str]
    include_columns: list[str]
    user_seeks: int
    user_scans: int
    avg_total_user_cost: float
    avg_user_impact: float
    recommended_index_name: str
    create_enabled: bool
    error_message: Optional[str] = None


class MissingIndexListOut(BaseModel):
    instance_id: uuid.UUID
    database_name: str
    checked_at: Optional[datetime] = None
    collection_status: str = "unknown"
    collection_error: Optional[str] = None
    stale: bool = True
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int
    items: list[MissingIndexItem]


class IndexCreateRequest(BaseModel):
    instance_id: uuid.UUID
    database_name: str = Field(min_length=1, max_length=128)
    schema_name: str = Field(min_length=1, max_length=128)
    table_name: str = Field(min_length=1, max_length=128)
    key_columns: list[str] = Field(min_length=1)
    include_columns: list[str] = Field(default_factory=list)
    index_name: str = Field(min_length=1, max_length=128)


class IndexCreateResponse(BaseModel):
    audit_id: uuid.UUID
    instance_id: uuid.UUID
    database_name: str
    schema_name: str
    table_name: str
    index_name: str
    result: IndexCreateResult
    error_message: Optional[str] = None


class IndexFragmentationItem(BaseModel):
    database_name: str
    schema_name: str
    table_name: str
    index_name: str
    index_type: str
    partition_number: int
    avg_fragmentation_in_percent: float
    page_count: int
    recommended_action: IndexFragmentationAction
    action_enabled: bool
    online_rebuild_supported: bool
    error_message: Optional[str] = None


class IndexFragmentationListOut(BaseModel):
    instance_id: uuid.UUID
    database_name: str
    checked_at: Optional[datetime] = None
    collection_status: str = "unknown"
    collection_error: Optional[str] = None
    stale: bool = True
    online_rebuild_supported: bool
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int
    items: list[IndexFragmentationItem]


class IndexFragmentationActionRequest(BaseModel):
    instance_id: uuid.UUID
    database_name: str = Field(min_length=1, max_length=128)
    schema_name: str = Field(min_length=1, max_length=128)
    table_name: str = Field(min_length=1, max_length=128)
    index_name: str = Field(min_length=1, max_length=128)
    partition_number: int = Field(ge=1)
    action: Literal["REORGANIZE", "REBUILD"]
    avg_fragmentation_in_percent: float = Field(ge=0)
    page_count: int = Field(ge=0)


class IndexFragmentationActionResponse(BaseModel):
    audit_id: uuid.UUID
    instance_id: uuid.UUID
    database_name: str
    schema_name: str
    table_name: str
    index_name: str
    partition_number: int
    action: Literal["REORGANIZE", "REBUILD"]
    online_used: bool
    result: IndexCreateResult
    error_message: Optional[str] = None


class IndexAuditOut(BaseModel):
    audit_id: uuid.UUID
    instance_id: uuid.UUID
    database_name: str
    schema_name: str
    table_name: str
    index_name: str
    action: str
    result: IndexCreateResult
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

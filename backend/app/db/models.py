from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Instance(Base):
    __tablename__ = "instances"
    __table_args__ = (
        CheckConstraint(
            "status IN ('online', 'offline', 'collect_error', 'disabled')",
            name="instances_status_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1433"))
    database_name: Mapped[Optional[str]] = mapped_column(String(128))
    environment: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'prod'"))
    encrypted_collect_dsn: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_kill_dsn: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'disabled'"))
    collect_interval_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("5")
    )
    missing_index_collect_interval_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("600")
    )
    index_fragmentation_collect_interval_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("600")
    )
    index_operation_timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1800")
    )
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("7"))
    business_owner: Mapped[Optional[str]] = mapped_column(String(128))
    dba_owner: Mapped[Optional[str]] = mapped_column(String(128))
    sqlserver_version: Mapped[Optional[str]] = mapped_column(String(128))
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InstanceCollectStatus(Base):
    __tablename__ = "instance_collect_status"

    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instances.id"), primary_key=True
    )
    last_success_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True))
    last_duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'unknown'"))
    error_code: Mapped[Optional[str]] = mapped_column(String(64))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    capabilities: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SnapshotFrame(Base):
    __tablename__ = "snapshot_frames"
    __table_args__ = (
        PrimaryKeyConstraint("id", "snapshot_time"),
        Index("idx_snapshot_frames_instance_time", "instance_id", text("snapshot_time DESC")),
        {"postgresql_partition_by": "RANGE (snapshot_time)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instances.id"), nullable=False
    )
    snapshot_time: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    collect_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    cpu_load_percent: Mapped[Optional[object]] = mapped_column(Numeric(5, 2))
    memory_usage_percent: Mapped[Optional[object]] = mapped_column(Numeric(5, 2))
    network_bytes_sent_total: Mapped[Optional[int]] = mapped_column(BigInteger)
    network_bytes_received_total: Mapped[Optional[int]] = mapped_column(BigInteger)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SessionSnapshot(Base):
    __tablename__ = "session_snapshots"
    __table_args__ = (
        PrimaryKeyConstraint("id", "snapshot_time"),
        Index("idx_session_snapshots_instance_time", "instance_id", text("snapshot_time DESC")),
        Index(
            "idx_session_snapshots_session_time",
            "instance_id",
            "session_id",
            text("snapshot_time DESC"),
        ),
        Index(
            "idx_session_snapshots_open_tran",
            "instance_id",
            text("snapshot_time DESC"),
            "open_transaction_count",
        ),
        {"postgresql_partition_by": "RANGE (snapshot_time)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # frame 对齐一致性由 Collector 单事务写入保证；后续分区化后再评估复合 FK。
    frame_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instances.id"), nullable=False
    )
    snapshot_time: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    login_name: Mapped[Optional[str]] = mapped_column(String(256))
    host_name: Mapped[Optional[str]] = mapped_column(String(256))
    program_name: Mapped[Optional[str]] = mapped_column(String(512))
    database_name: Mapped[Optional[str]] = mapped_column(String(128))
    status: Mapped[Optional[str]] = mapped_column(String(64))
    open_transaction_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    login_time: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True))
    last_request_start_time: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True))
    last_request_end_time: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True))
    cpu_time: Mapped[Optional[int]] = mapped_column(BigInteger)
    reads: Mapped[Optional[int]] = mapped_column(BigInteger)
    writes: Mapped[Optional[int]] = mapped_column(BigInteger)
    logical_reads: Mapped[Optional[int]] = mapped_column(BigInteger)
    current_sql_hash: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RequestSnapshot(Base):
    __tablename__ = "request_snapshots"
    __table_args__ = (
        PrimaryKeyConstraint("id", "snapshot_time"),
        Index("idx_request_snapshots_instance_time", "instance_id", text("snapshot_time DESC")),
        Index(
            "idx_request_snapshots_cpu",
            "instance_id",
            text("snapshot_time DESC"),
            text("cpu_time_ms DESC"),
        ),
        Index(
            "idx_request_snapshots_io",
            "instance_id",
            text("snapshot_time DESC"),
            text("logical_reads DESC"),
        ),
        Index(
            "idx_request_snapshots_blocking",
            "instance_id",
            text("snapshot_time DESC"),
            "blocking_session_id",
        ),
        {"postgresql_partition_by": "RANGE (snapshot_time)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # frame 对齐一致性由 Collector 单事务写入保证；后续分区化后再评估复合 FK。
    frame_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instances.id"), nullable=False
    )
    snapshot_time: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    request_id: Mapped[Optional[int]] = mapped_column(Integer)
    database_name: Mapped[Optional[str]] = mapped_column(String(128))
    status: Mapped[Optional[str]] = mapped_column(String(64))
    command: Mapped[Optional[str]] = mapped_column(String(128))
    start_time: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[Optional[int]] = mapped_column(BigInteger)
    cpu_time_ms: Mapped[Optional[int]] = mapped_column(BigInteger)
    total_elapsed_time_ms: Mapped[Optional[int]] = mapped_column(BigInteger)
    reads: Mapped[Optional[int]] = mapped_column(BigInteger)
    writes: Mapped[Optional[int]] = mapped_column(BigInteger)
    logical_reads: Mapped[Optional[int]] = mapped_column(BigInteger)
    row_count: Mapped[Optional[int]] = mapped_column(BigInteger)
    wait_type: Mapped[Optional[str]] = mapped_column(String(128))
    wait_time_ms: Mapped[Optional[int]] = mapped_column(BigInteger)
    blocking_session_id: Mapped[Optional[int]] = mapped_column(Integer)
    percent_complete: Mapped[Optional[object]] = mapped_column(Numeric(5, 2))
    sql_hash: Mapped[Optional[str]] = mapped_column(String(64))
    normalized_sql_hash: Mapped[Optional[str]] = mapped_column(String(64))
    plan_handle: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    statement_start_offset: Mapped[Optional[int]] = mapped_column(Integer)
    statement_end_offset: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WaitSnapshot(Base):
    __tablename__ = "wait_snapshots"
    __table_args__ = (
        PrimaryKeyConstraint("id", "snapshot_time"),
        Index("idx_wait_snapshots_instance_time", "instance_id", text("snapshot_time DESC")),
        {"postgresql_partition_by": "RANGE (snapshot_time)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # frame 对齐一致性由 Collector 单事务写入保证；后续分区化后再评估复合 FK。
    frame_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instances.id"), nullable=False
    )
    snapshot_time: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    wait_type: Mapped[str] = mapped_column(String(128), nullable=False)
    wait_category: Mapped[str] = mapped_column(String(64), nullable=False)
    waiting_tasks_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_wait_time_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_wait_time_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BlockingSnapshot(Base):
    __tablename__ = "blocking_snapshots"
    __table_args__ = (
        PrimaryKeyConstraint("id", "snapshot_time"),
        Index("idx_blocking_snapshots_instance_time", "instance_id", text("snapshot_time DESC")),
        {"postgresql_partition_by": "RANGE (snapshot_time)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # frame 对齐一致性由 Collector 单事务写入保证；后续分区化后再评估复合 FK。
    frame_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instances.id"), nullable=False
    )
    snapshot_time: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    root_session_id: Mapped[Optional[int]] = mapped_column(Integer)
    blocking_session_id: Mapped[Optional[int]] = mapped_column(Integer)
    blocked_session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    chain_depth: Mapped[int] = mapped_column(Integer, nullable=False)
    blocked_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_wait_time_ms: Mapped[Optional[int]] = mapped_column(BigInteger)
    wait_type: Mapped[Optional[str]] = mapped_column(String(128))
    resource_description: Mapped[Optional[str]] = mapped_column(Text)
    cycle_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    special_blocker_code: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SqlText(Base):
    __tablename__ = "sql_texts"
    __table_args__ = (Index("idx_sql_texts_normalized_hash", "normalized_sql_hash"),)

    sql_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    normalized_sql_hash: Mapped[Optional[str]] = mapped_column(String(64))
    sql_text: Mapped[str] = mapped_column(Text, nullable=False)
    sql_preview: Mapped[Optional[str]] = mapped_column(String(512))
    first_seen_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)


class KillAudit(Base):
    __tablename__ = "kill_audits"
    __table_args__ = (
        CheckConstraint(
            "result IN ('success', 'failed', 'rejected')",
            name="kill_audits_result_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    operator_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    operator_name: Mapped[str] = mapped_column(String(128), nullable=False)
    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instances.id"), nullable=False
    )
    session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    before_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MissingIndexAudit(Base):
    __tablename__ = "missing_index_audits"
    __table_args__ = (
        CheckConstraint(
            "result IN ('running', 'success', 'failed', 'rejected')",
            name="missing_index_audits_result_check",
        ),
        Index("idx_missing_index_audits_instance_time", "instance_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    operator_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    operator_name: Mapped[str] = mapped_column(String(128), nullable=False)
    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instances.id"), nullable=False
    )
    database_name: Mapped[str] = mapped_column(String(128), nullable=False)
    schema_name: Mapped[str] = mapped_column(String(128), nullable=False)
    table_name: Mapped[str] = mapped_column(String(128), nullable=False)
    index_name: Mapped[str] = mapped_column(String(128), nullable=False)
    key_columns: Mapped[list] = mapped_column(JSONB, nullable=False)
    include_columns: Mapped[list] = mapped_column(JSONB, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'CREATE'"))
    partition_number: Mapped[Optional[int]] = mapped_column(Integer)
    online_used: Mapped[Optional[bool]] = mapped_column(Boolean)
    fragmentation_percent: Mapped[Optional[object]] = mapped_column(Numeric(9, 2))
    page_count: Mapped[Optional[int]] = mapped_column(BigInteger)
    ddl_summary: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IndexCollectionStatus(Base):
    __tablename__ = "index_collection_status"
    __table_args__ = (
        CheckConstraint(
            "index_type IN ('missing', 'fragmentation')",
            name="index_collection_status_type_check",
        ),
        CheckConstraint(
            "status IN ('unknown', 'success', 'failed')",
            name="index_collection_status_status_check",
        ),
        PrimaryKeyConstraint("instance_id", "database_name", "index_type"),
        Index("idx_index_collection_status_instance_type", "instance_id", "index_type"),
    )

    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instances.id"), nullable=False
    )
    database_name: Mapped[str] = mapped_column(String(128), nullable=False)
    index_type: Mapped[str] = mapped_column(String(32), nullable=False)
    last_success_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'unknown'"))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MissingIndexSnapshot(Base):
    __tablename__ = "missing_index_snapshots"
    __table_args__ = (
        Index("idx_missing_index_snapshots_instance_database", "instance_id", "database_name"),
        Index(
            "idx_missing_index_snapshots_page",
            "instance_id",
            "database_name",
            text("avg_total_user_cost DESC"),
            text("id ASC"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instances.id"), nullable=False
    )
    database_name: Mapped[str] = mapped_column(String(128), nullable=False)
    schema_name: Mapped[str] = mapped_column(String(128), nullable=False)
    table_name: Mapped[str] = mapped_column(String(128), nullable=False)
    equality_columns: Mapped[list] = mapped_column(JSONB, nullable=False)
    inequality_columns: Mapped[list] = mapped_column(JSONB, nullable=False)
    include_columns: Mapped[list] = mapped_column(JSONB, nullable=False)
    user_seeks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_scans: Mapped[int] = mapped_column(BigInteger, nullable=False)
    avg_total_user_cost: Mapped[object] = mapped_column(Numeric(18, 4), nullable=False)
    avg_user_impact: Mapped[object] = mapped_column(Numeric(9, 2), nullable=False)
    recommended_index_name: Mapped[str] = mapped_column(String(128), nullable=False)
    collected_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IndexFragmentationSnapshot(Base):
    __tablename__ = "index_fragmentation_snapshots"
    __table_args__ = (
        Index(
            "idx_index_fragmentation_snapshots_instance_database",
            "instance_id",
            "database_name",
        ),
        Index(
            "idx_index_fragmentation_snapshots_page",
            "instance_id",
            "database_name",
            text("avg_fragmentation_in_percent DESC"),
            text("id ASC"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instances.id"), nullable=False
    )
    database_name: Mapped[str] = mapped_column(String(128), nullable=False)
    schema_name: Mapped[str] = mapped_column(String(128), nullable=False)
    table_name: Mapped[str] = mapped_column(String(128), nullable=False)
    index_name: Mapped[str] = mapped_column(String(128), nullable=False)
    index_type: Mapped[str] = mapped_column(String(128), nullable=False)
    partition_number: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_fragmentation_in_percent: Mapped[object] = mapped_column(Numeric(9, 2), nullable=False)
    page_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    recommended_action: Mapped[str] = mapped_column(String(32), nullable=False)
    online_rebuild_supported: Mapped[bool] = mapped_column(Boolean, nullable=False)
    collected_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('viewer', 'developer', 'dba', 'admin')",
            name="users_role_check",
        ),
        CheckConstraint("status IN ('active', 'disabled')", name="users_status_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    username: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'active'"))
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

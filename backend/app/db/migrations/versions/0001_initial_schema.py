"""初始数据库结构。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), server_default=sa.text("1433"), nullable=False),
        sa.Column("database_name", sa.String(length=128), nullable=True),
        sa.Column("environment", sa.String(length=32), server_default=sa.text("'prod'"), nullable=False),
        sa.Column("encrypted_collect_dsn", sa.Text(), nullable=False),
        sa.Column("encrypted_kill_dsn", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'disabled'"), nullable=False),
        sa.Column(
            "collect_interval_seconds",
            sa.Integer(),
            server_default=sa.text("5"),
            nullable=False,
        ),
        sa.Column("retention_days", sa.Integer(), server_default=sa.text("7"), nullable=False),
        sa.Column("business_owner", sa.String(length=128), nullable=True),
        sa.Column("dba_owner", sa.String(length=128), nullable=True),
        sa.Column("sqlserver_version", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('online', 'offline', 'collect_error', 'disabled')",
            name="instances_status_check",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "sql_texts",
        sa.Column("sql_hash", sa.String(length=64), nullable=False),
        sa.Column("normalized_sql_hash", sa.String(length=64), nullable=True),
        sa.Column("sql_text", sa.Text(), nullable=False),
        sa.Column("sql_preview", sa.String(length=512), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("sql_hash"),
    )
    op.create_index("idx_sql_texts_normalized_hash", "sql_texts", ["normalized_sql_hash"])
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'active'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "role IN ('viewer', 'developer', 'dba', 'admin')",
            name="users_role_check",
        ),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="users_status_check"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "instance_collect_status",
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_duration_ms", sa.Integer(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'unknown'"), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("capabilities", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["instance_id"], ["instances.id"]),
        sa.PrimaryKeyConstraint("instance_id"),
    )
    op.create_table(
        "kill_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operator_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operator_name", sa.String(length=128), nullable=False),
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("before_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "result IN ('success', 'failed', 'rejected')",
            name="kill_audits_result_check",
        ),
        sa.ForeignKeyConstraint(["instance_id"], ["instances.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "snapshot_frames",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collect_duration_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["instance_id"], ["instances.id"]),
        sa.PrimaryKeyConstraint("id", "snapshot_time"),
        postgresql_partition_by="RANGE (snapshot_time)",
    )
    op.create_table(
        "session_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("frame_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("login_name", sa.String(length=256), nullable=True),
        sa.Column("host_name", sa.String(length=256), nullable=True),
        sa.Column("program_name", sa.String(length=512), nullable=True),
        sa.Column("database_name", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("open_transaction_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("login_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_request_start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_request_end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cpu_time", sa.BigInteger(), nullable=True),
        sa.Column("reads", sa.BigInteger(), nullable=True),
        sa.Column("writes", sa.BigInteger(), nullable=True),
        sa.Column("logical_reads", sa.BigInteger(), nullable=True),
        sa.Column("current_sql_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["instance_id"], ["instances.id"]),
        sa.PrimaryKeyConstraint("id", "snapshot_time"),
        postgresql_partition_by="RANGE (snapshot_time)",
    )
    op.create_index("idx_session_snapshots_instance_time", "session_snapshots", ["instance_id", sa.text("snapshot_time DESC")])
    op.create_index("idx_session_snapshots_session_time", "session_snapshots", ["instance_id", "session_id", sa.text("snapshot_time DESC")])
    op.create_index("idx_session_snapshots_open_tran", "session_snapshots", ["instance_id", sa.text("snapshot_time DESC"), "open_transaction_count"])
    op.create_table(
        "request_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("frame_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=True),
        sa.Column("database_name", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("command", sa.String(length=128), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("cpu_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("total_elapsed_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("reads", sa.BigInteger(), nullable=True),
        sa.Column("writes", sa.BigInteger(), nullable=True),
        sa.Column("logical_reads", sa.BigInteger(), nullable=True),
        sa.Column("row_count", sa.BigInteger(), nullable=True),
        sa.Column("wait_type", sa.String(length=128), nullable=True),
        sa.Column("wait_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("blocking_session_id", sa.Integer(), nullable=True),
        sa.Column("percent_complete", sa.Numeric(5, 2), nullable=True),
        sa.Column("sql_hash", sa.String(length=64), nullable=True),
        sa.Column("normalized_sql_hash", sa.String(length=64), nullable=True),
        sa.Column("plan_handle", sa.LargeBinary(), nullable=True),
        sa.Column("statement_start_offset", sa.Integer(), nullable=True),
        sa.Column("statement_end_offset", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["instance_id"], ["instances.id"]),
        sa.PrimaryKeyConstraint("id", "snapshot_time"),
        postgresql_partition_by="RANGE (snapshot_time)",
    )
    op.create_index("idx_request_snapshots_instance_time", "request_snapshots", ["instance_id", sa.text("snapshot_time DESC")])
    op.create_index("idx_request_snapshots_cpu", "request_snapshots", ["instance_id", sa.text("snapshot_time DESC"), sa.text("cpu_time_ms DESC")])
    op.create_index("idx_request_snapshots_io", "request_snapshots", ["instance_id", sa.text("snapshot_time DESC"), sa.text("logical_reads DESC")])
    op.create_index("idx_request_snapshots_blocking", "request_snapshots", ["instance_id", sa.text("snapshot_time DESC"), "blocking_session_id"])
    op.create_table(
        "wait_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("frame_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("wait_type", sa.String(length=128), nullable=False),
        sa.Column("wait_category", sa.String(length=64), nullable=False),
        sa.Column("waiting_tasks_count", sa.Integer(), nullable=False),
        sa.Column("total_wait_time_ms", sa.BigInteger(), nullable=False),
        sa.Column("max_wait_time_ms", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["instance_id"], ["instances.id"]),
        sa.PrimaryKeyConstraint("id", "snapshot_time"),
        postgresql_partition_by="RANGE (snapshot_time)",
    )
    op.create_table(
        "blocking_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("frame_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("root_session_id", sa.Integer(), nullable=True),
        sa.Column("blocking_session_id", sa.Integer(), nullable=True),
        sa.Column("blocked_session_id", sa.Integer(), nullable=False),
        sa.Column("chain_depth", sa.Integer(), nullable=False),
        sa.Column("blocked_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_wait_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("wait_type", sa.String(length=128), nullable=True),
        sa.Column("resource_description", sa.Text(), nullable=True),
        sa.Column("cycle_detected", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("special_blocker_code", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["instance_id"], ["instances.id"]),
        sa.PrimaryKeyConstraint("id", "snapshot_time"),
        postgresql_partition_by="RANGE (snapshot_time)",
    )


def downgrade() -> None:
    op.drop_table("blocking_snapshots")
    op.drop_table("wait_snapshots")
    op.drop_index("idx_request_snapshots_blocking", table_name="request_snapshots")
    op.drop_index("idx_request_snapshots_io", table_name="request_snapshots")
    op.drop_index("idx_request_snapshots_cpu", table_name="request_snapshots")
    op.drop_index("idx_request_snapshots_instance_time", table_name="request_snapshots")
    op.drop_table("request_snapshots")
    op.drop_index("idx_session_snapshots_open_tran", table_name="session_snapshots")
    op.drop_index("idx_session_snapshots_session_time", table_name="session_snapshots")
    op.drop_index("idx_session_snapshots_instance_time", table_name="session_snapshots")
    op.drop_table("session_snapshots")
    op.drop_table("snapshot_frames")
    op.drop_table("kill_audits")
    op.drop_table("instance_collect_status")
    op.drop_table("users")
    op.drop_index("idx_sql_texts_normalized_hash", table_name="sql_texts")
    op.drop_table("sql_texts")
    op.drop_table("instances")

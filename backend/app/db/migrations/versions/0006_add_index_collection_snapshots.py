"""新增索引采集快照。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006_index_snapshots"
down_revision = "0005_split_network_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "instances",
        sa.Column(
            "missing_index_collect_interval_seconds",
            sa.Integer(),
            server_default=sa.text("600"),
            nullable=False,
        ),
    )
    op.add_column(
        "instances",
        sa.Column(
            "index_fragmentation_collect_interval_seconds",
            sa.Integer(),
            server_default=sa.text("600"),
            nullable=False,
        ),
    )
    op.create_table(
        "index_collection_status",
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("database_name", sa.String(length=128), nullable=False),
        sa.Column("index_type", sa.String(length=32), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'unknown'"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("item_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "index_type IN ('missing', 'fragmentation')",
            name="index_collection_status_type_check",
        ),
        sa.CheckConstraint(
            "status IN ('unknown', 'success', 'failed')",
            name="index_collection_status_status_check",
        ),
        sa.ForeignKeyConstraint(["instance_id"], ["instances.id"]),
        sa.PrimaryKeyConstraint("instance_id", "database_name", "index_type"),
    )
    op.create_index(
        "idx_index_collection_status_instance_type",
        "index_collection_status",
        ["instance_id", "index_type"],
    )
    op.create_table(
        "missing_index_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("database_name", sa.String(length=128), nullable=False),
        sa.Column("schema_name", sa.String(length=128), nullable=False),
        sa.Column("table_name", sa.String(length=128), nullable=False),
        sa.Column("equality_columns", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("inequality_columns", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("include_columns", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("user_seeks", sa.BigInteger(), nullable=False),
        sa.Column("user_scans", sa.BigInteger(), nullable=False),
        sa.Column("avg_total_user_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("avg_user_impact", sa.Numeric(9, 2), nullable=False),
        sa.Column("recommended_index_name", sa.String(length=128), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["instance_id"], ["instances.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_missing_index_snapshots_instance_database",
        "missing_index_snapshots",
        ["instance_id", "database_name"],
    )
    op.create_table(
        "index_fragmentation_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("database_name", sa.String(length=128), nullable=False),
        sa.Column("schema_name", sa.String(length=128), nullable=False),
        sa.Column("table_name", sa.String(length=128), nullable=False),
        sa.Column("index_name", sa.String(length=128), nullable=False),
        sa.Column("index_type", sa.String(length=128), nullable=False),
        sa.Column("partition_number", sa.Integer(), nullable=False),
        sa.Column("avg_fragmentation_in_percent", sa.Numeric(9, 2), nullable=False),
        sa.Column("page_count", sa.BigInteger(), nullable=False),
        sa.Column("recommended_action", sa.String(length=32), nullable=False),
        sa.Column("online_rebuild_supported", sa.Boolean(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["instance_id"], ["instances.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_index_fragmentation_snapshots_instance_database",
        "index_fragmentation_snapshots",
        ["instance_id", "database_name"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_index_fragmentation_snapshots_instance_database",
        table_name="index_fragmentation_snapshots",
    )
    op.drop_table("index_fragmentation_snapshots")
    op.drop_index("idx_missing_index_snapshots_instance_database", table_name="missing_index_snapshots")
    op.drop_table("missing_index_snapshots")
    op.drop_index("idx_index_collection_status_instance_type", table_name="index_collection_status")
    op.drop_table("index_collection_status")
    op.drop_column("instances", "index_fragmentation_collect_interval_seconds")
    op.drop_column("instances", "missing_index_collect_interval_seconds")

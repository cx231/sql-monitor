"""新增缺失索引操作审计。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0004_missing_index_audits"
down_revision = "0003_snapshot_resource_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "missing_index_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operator_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operator_name", sa.String(length=128), nullable=False),
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("database_name", sa.String(length=128), nullable=False),
        sa.Column("schema_name", sa.String(length=128), nullable=False),
        sa.Column("table_name", sa.String(length=128), nullable=False),
        sa.Column("index_name", sa.String(length=128), nullable=False),
        sa.Column("key_columns", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("include_columns", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("action", sa.String(length=32), server_default=sa.text("'CREATE'"), nullable=False),
        sa.Column("partition_number", sa.Integer(), nullable=True),
        sa.Column("online_used", sa.Boolean(), nullable=True),
        sa.Column("fragmentation_percent", sa.Numeric(9, 2), nullable=True),
        sa.Column("page_count", sa.BigInteger(), nullable=True),
        sa.Column("ddl_summary", sa.Text(), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "result IN ('success', 'failed', 'rejected')",
            name="missing_index_audits_result_check",
        ),
        sa.ForeignKeyConstraint(["instance_id"], ["instances.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_missing_index_audits_instance_time",
        "missing_index_audits",
        ["instance_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_missing_index_audits_instance_time", table_name="missing_index_audits")
    op.drop_table("missing_index_audits")

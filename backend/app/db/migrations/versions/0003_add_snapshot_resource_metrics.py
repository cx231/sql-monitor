"""为快照帧增加资源指标。"""

from alembic import op
import sqlalchemy as sa


revision = "0003_snapshot_resource_metrics"
down_revision = "0002_seed_default_admin_user"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "snapshot_frames",
        sa.Column("cpu_load_percent", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "snapshot_frames",
        sa.Column("memory_usage_percent", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "snapshot_frames",
        sa.Column("network_bytes_total", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("snapshot_frames", "network_bytes_total")
    op.drop_column("snapshot_frames", "memory_usage_percent")
    op.drop_column("snapshot_frames", "cpu_load_percent")

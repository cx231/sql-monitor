"""拆分网络发送和接收资源指标。"""

from alembic import op
import sqlalchemy as sa


revision = "0005_split_network_metrics"
down_revision = "0004_missing_index_audits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "snapshot_frames",
        sa.Column("network_bytes_sent_total", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "snapshot_frames",
        sa.Column("network_bytes_received_total", sa.BigInteger(), nullable=True),
    )
    op.drop_column("snapshot_frames", "network_bytes_total")


def downgrade() -> None:
    op.add_column(
        "snapshot_frames",
        sa.Column("network_bytes_total", sa.BigInteger(), nullable=True),
    )
    op.drop_column("snapshot_frames", "network_bytes_received_total")
    op.drop_column("snapshot_frames", "network_bytes_sent_total")

"""新增索引快照分页索引。"""

from alembic import op
import sqlalchemy as sa


revision = "0007_index_page_indexes"
down_revision = "0006_index_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_missing_index_snapshots_page",
        "missing_index_snapshots",
        ["instance_id", "database_name", sa.text("avg_total_user_cost DESC"), sa.text("id ASC")],
    )
    op.create_index(
        "idx_index_fragmentation_snapshots_page",
        "index_fragmentation_snapshots",
        [
            "instance_id",
            "database_name",
            sa.text("avg_fragmentation_in_percent DESC"),
            sa.text("id ASC"),
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_index_fragmentation_snapshots_page",
        table_name="index_fragmentation_snapshots",
    )
    op.drop_index("idx_missing_index_snapshots_page", table_name="missing_index_snapshots")

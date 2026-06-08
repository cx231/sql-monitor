"""异步索引 DDL 与实例超时配置。"""

from alembic import op
import sqlalchemy as sa


revision = "0008_async_index_ddl"
down_revision = "0007_index_page_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "instances",
        sa.Column(
            "index_operation_timeout_seconds",
            sa.Integer(),
            server_default=sa.text("1800"),
            nullable=False,
        ),
    )
    op.drop_constraint(
        "missing_index_audits_result_check",
        "missing_index_audits",
        type_="check",
    )
    op.create_check_constraint(
        "missing_index_audits_result_check",
        "missing_index_audits",
        "result IN ('running', 'success', 'failed', 'rejected')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "missing_index_audits_result_check",
        "missing_index_audits",
        type_="check",
    )
    op.create_check_constraint(
        "missing_index_audits_result_check",
        "missing_index_audits",
        "result IN ('success', 'failed', 'rejected')",
    )
    op.drop_column("instances", "index_operation_timeout_seconds")

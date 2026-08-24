"""preserve strategy allocation input mode

Revision ID: d5f6a7b8c9d0
Revises: c4e5f6a7b8c9
"""

from alembic import op
import sqlalchemy as sa


revision = "d5f6a7b8c9d0"
down_revision = "c4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_strategy",
        sa.Column(
            "allocation_mode",
            sa.String(length=16),
            nullable=False,
            server_default="ratio",
        ),
    )
    op.create_check_constraint(
        "ck_user_strategy_allocation_mode",
        "user_strategy",
        "allocation_mode IN ('ratio', 'amount')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_user_strategy_allocation_mode",
        "user_strategy",
        type_="check",
    )
    op.drop_column("user_strategy", "allocation_mode")

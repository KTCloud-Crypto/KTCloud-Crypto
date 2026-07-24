"""add strategy pause

Revision ID: 8f3c6d1a2b40
Revises: 267a2d5d2f22
Create Date: 2026-07-23 17:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8f3c6d1a2b40"
down_revision: Union[str, None] = "267a2d5d2f22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_strategy",
        sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("user_strategy", "paused", server_default=None)


def downgrade() -> None:
    op.drop_column("user_strategy", "paused")

"""add strategy subscription event

Revision ID: a3d9f1c8b2e4
Revises: f9c0d1e2a3b4
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3d9f1c8b2e4"
down_revision: Union[str, tuple[str, str], None] = "f9c0d1e2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "strategy_subscription_event",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("strategy_id", sa.Integer(), sa.ForeignKey("strategy.id"), nullable=False, index=True),
        sa.Column("market_id", sa.Integer(), sa.ForeignKey("supported_market.id"), nullable=False, index=True),
        sa.Column("mode", sa.String(length=16), nullable=False, index=True),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("timeframe_minutes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("strategy_subscription_event")
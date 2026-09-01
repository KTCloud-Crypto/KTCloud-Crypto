"""add Trading-owned execution request

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trading_execution_request",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("user_strategy_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=8), nullable=False),
        sa.Column("market", sa.String(length=20), nullable=False),
        sa.Column("reference_price", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["user_strategy_id"], ["user_strategy.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_trading_execution_request_id", "trading_execution_request", ["id"])
    op.create_index("ix_trading_execution_request_mode", "trading_execution_request", ["mode"])
    op.create_index(
        "ix_trading_execution_request_user_id", "trading_execution_request", ["user_id"]
    )
    op.create_index(
        "ix_trading_execution_request_user_strategy_id",
        "trading_execution_request",
        ["user_strategy_id"],
    )
    op.alter_column("strategy_execution", "signal_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("strategy_execution", sa.Column("execution_request_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_strategy_execution_execution_request",
        "strategy_execution",
        "trading_execution_request",
        ["execution_request_id"],
        ["id"],
    )
    op.create_index(
        "ix_strategy_execution_execution_request_id",
        "strategy_execution",
        ["execution_request_id"],
        unique=True,
    )
    op.create_check_constraint(
        "ck_strategy_execution_single_origin",
        "strategy_execution",
        "(signal_id IS NOT NULL) <> (execution_request_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_strategy_execution_single_origin", "strategy_execution", type_="check")
    op.drop_index("ix_strategy_execution_execution_request_id", table_name="strategy_execution")
    op.drop_constraint(
        "fk_strategy_execution_execution_request", "strategy_execution", type_="foreignkey"
    )
    op.drop_column("strategy_execution", "execution_request_id")
    op.alter_column("strategy_execution", "signal_id", existing_type=sa.Integer(), nullable=False)
    op.drop_index("ix_trading_execution_request_user_strategy_id", table_name="trading_execution_request")
    op.drop_index("ix_trading_execution_request_user_id", table_name="trading_execution_request")
    op.drop_index("ix_trading_execution_request_mode", table_name="trading_execution_request")
    op.drop_index("ix_trading_execution_request_id", table_name="trading_execution_request")
    op.drop_table("trading_execution_request")

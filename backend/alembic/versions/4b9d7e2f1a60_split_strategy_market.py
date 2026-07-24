"""split strategy definition from supported market

Revision ID: 4b9d7e2f1a60
Revises: 8f3c6d1a2b40
Create Date: 2026-07-23 18:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4b9d7e2f1a60"
down_revision: Union[str, None] = "8f3c6d1a2b40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MARKETS = [
    ("KRW-BTC", "비트코인"),
    ("KRW-ETH", "이더리움"),
    ("KRW-XRP", "리플"),
    ("KRW-SOL", "솔라나"),
    ("KRW-DOGE", "도지코인"),
    ("KRW-ADA", "에이다"),
    ("KRW-AVAX", "아발란체"),
    ("KRW-LINK", "체인링크"),
    ("KRW-DOT", "폴카닷"),
    ("KRW-TRX", "트론"),
]


def upgrade() -> None:
    op.create_table(
        "supported_market",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("display_name", sa.String(length=50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_supported_market_id", "supported_market", ["id"])
    op.create_index("ix_supported_market_code", "supported_market", ["code"], unique=True)
    market_table = sa.table(
        "supported_market",
        sa.column("code", sa.String),
        sa.column("display_name", sa.String),
        sa.column("enabled", sa.Boolean),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(market_table, [
        {"code": code, "display_name": name, "enabled": True, "sort_order": index}
        for index, (code, name) in enumerate(MARKETS, start=1)
    ])

    op.add_column("user_strategy", sa.Column("market_id", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE user_strategy SET market_id = "
        "(SELECT id FROM supported_market WHERE code = 'KRW-BTC')"
    )
    op.alter_column("user_strategy", "market_id", nullable=False)
    op.create_foreign_key(
        "fk_user_strategy_market",
        "user_strategy",
        "supported_market",
        ["market_id"],
        ["id"],
    )
    op.create_index("ix_user_strategy_market_id", "user_strategy", ["market_id"])
    op.drop_constraint("uq_user_strategy_mode", "user_strategy", type_="unique")
    op.create_unique_constraint(
        "uq_user_strategy_market_mode",
        "user_strategy",
        ["user_id", "strategy_id", "market_id", "mode"],
    )

    op.drop_constraint(
        "uq_strategy_runtime_strategy_timeframe",
        "strategy_runtime",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_strategy_runtime_market_timeframe",
        "strategy_runtime",
        ["strategy_id", "market", "timeframe_minutes"],
    )
    op.drop_constraint(
        "uq_strategy_signal_candle_action",
        "strategy_signal",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_strategy_signal_market_candle_action",
        "strategy_signal",
        ["strategy_id", "market", "timeframe_minutes", "candle_open_time", "action"],
    )
    op.drop_column("strategy", "market")


def downgrade() -> None:
    op.add_column(
        "strategy",
        sa.Column("market", sa.String(length=20), nullable=False, server_default="KRW-BTC"),
    )
    op.alter_column("strategy", "market", server_default=None)
    op.drop_constraint(
        "uq_strategy_signal_market_candle_action",
        "strategy_signal",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_strategy_signal_candle_action",
        "strategy_signal",
        ["strategy_id", "timeframe_minutes", "candle_open_time", "action"],
    )
    op.drop_constraint(
        "uq_strategy_runtime_market_timeframe",
        "strategy_runtime",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_strategy_runtime_strategy_timeframe",
        "strategy_runtime",
        ["strategy_id", "timeframe_minutes"],
    )
    op.drop_constraint("uq_user_strategy_market_mode", "user_strategy", type_="unique")
    op.create_unique_constraint(
        "uq_user_strategy_mode",
        "user_strategy",
        ["user_id", "strategy_id", "mode"],
    )
    op.drop_index("ix_user_strategy_market_id", table_name="user_strategy")
    op.drop_constraint("fk_user_strategy_market", "user_strategy", type_="foreignkey")
    op.drop_column("user_strategy", "market_id")
    op.drop_index("ix_supported_market_code", table_name="supported_market")
    op.drop_index("ix_supported_market_id", table_name="supported_market")
    op.drop_table("supported_market")

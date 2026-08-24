"""store actual exchange fee on strategy executions

Revision ID: e6a7b8c9d0e1
Revises: d5f6a7b8c9d0
"""

from alembic import op
import sqlalchemy as sa


revision = "e6a7b8c9d0e1"
down_revision = "d5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "strategy_execution",
        sa.Column("paid_fee", sa.Float(), nullable=True),
    )
    # 기존 성공 체결은 이미 보존 중인 Upbit 주문 원문에서 실제 납부
    # 수수료를 복구합니다. 원문이나 필드가 없는 legacy 행은 NULL로 남겨
    # 계산 시 기본 수수료율 fallback을 사용합니다.
    op.execute("""
        UPDATE strategy_execution AS execution
        SET paid_fee = NULLIF(trade.raw_response ->> 'paid_fee', '')::double precision
        FROM trade
        WHERE trade.strategy_execution_id = execution.id
          AND trade.raw_response IS NOT NULL
          AND trade.raw_response ->> 'paid_fee' IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_column("strategy_execution", "paid_fee")

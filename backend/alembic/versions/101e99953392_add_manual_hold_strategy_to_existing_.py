"""add manual hold strategy to existing users

Revision ID: 101e99953392
Revises: bad304ee5eec
Create Date: 2026-07-27 04:58:22.802408
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '101e99953392'
down_revision: Union[str, None] = 'bad304ee5eec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 기존 사용자들에게 "미배정 자산" 전략 추가
    op.execute("""
        INSERT INTO user_strategy (user_id, strategy_id, market_id, timeframe_minutes, mode, enabled, invest_ratio, paused, created_at, updated_at)
        SELECT
            u.id as user_id,
            s.id as strategy_id,
            m.id as market_id,
            10 as timeframe_minutes,
            'live' as mode,
            true as enabled,
            0.0 as invest_ratio,
            false as paused,
            NOW() as created_at,
            NOW() as updated_at
        FROM "user" u
        CROSS JOIN (SELECT id FROM strategy WHERE code = 'manual_hold_v1') s
        CROSS JOIN (SELECT id FROM supported_market WHERE enabled = true) m
        WHERE NOT EXISTS (
            SELECT 1 FROM user_strategy us
            WHERE us.user_id = u.id
            AND us.strategy_id = s.id
            AND us.market_id = m.id
        )
    """)


def downgrade() -> None:
    # 롤백: 미배정 자산 전략 제거 (invest_ratio가 0.0인 manual_hold_v1만)
    op.execute("""
        DELETE FROM user_strategy
        WHERE strategy_id IN (SELECT id FROM strategy WHERE code = 'manual_hold_v1')
        AND invest_ratio = 0.0
    """)

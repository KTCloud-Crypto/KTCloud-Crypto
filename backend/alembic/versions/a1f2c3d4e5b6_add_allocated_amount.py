"""add allocated amount to user strategy
 
Revision ID: a1f2c3d4e5b6
Revises: 101e99953392
Create Date: 2026-07-28
 
구독 시점의 자유 잔고를 기준으로 산정한 주문 예산을 저장합니다.
NULL이면 기존 총자산 비율 방식으로 폴백해 계산 후 채워집니다.
"""
from alembic import op
import sqlalchemy as sa
 
 
revision = "a1f2c3d4e5b6"
down_revision = "d66b5ff3b99a"
branch_labels = None
depends_on = None
 
 
def upgrade() -> None:
    op.add_column(
        "user_strategy",
        sa.Column("allocated_amount", sa.Float(), nullable=True),
    )
 
 
def downgrade() -> None:
    op.drop_column("user_strategy", "allocated_amount")
 
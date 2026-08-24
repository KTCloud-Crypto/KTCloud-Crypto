"""make position sync adjustments an independent attribution ledger

Revision ID: c4e5f6a7b8c9
Revises: a3d9f1c8b2e4
Create Date: 2026-08-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e5f6a7b8c9"
down_revision: Union[str, None] = "a3d9f1c8b2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "position_sync_adjustment",
        "strategy_execution_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.add_column(
        "position_sync_adjustment",
        sa.Column(
            "cost_basis_source",
            sa.String(length=32),
            nullable=False,
            server_default="legacy_exchange_average",
        ),
    )
    op.add_column(
        "position_sync_adjustment",
        sa.Column("reason", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "position_sync_adjustment",
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_position_sync_adjustment_idempotency_key",
        "position_sync_adjustment",
        ["idempotency_key"],
        unique=True,
    )
    op.create_check_constraint(
        "ck_position_sync_adjustment_volume_positive",
        "position_sync_adjustment",
        "volume > 0",
    )
    op.execute(
        "UPDATE position_sync_adjustment SET action = 'assign' WHERE action = 'buy'"
    )
    op.execute(
        "UPDATE position_sync_adjustment SET action = 'deduct' WHERE action = 'sell'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE position_sync_adjustment SET action = 'buy' WHERE action = 'assign'"
    )
    op.execute(
        "UPDATE position_sync_adjustment SET action = 'sell' WHERE action = 'deduct'"
    )
    op.drop_constraint(
        "ck_position_sync_adjustment_volume_positive",
        "position_sync_adjustment",
        type_="check",
    )
    op.drop_index(
        "ix_position_sync_adjustment_idempotency_key",
        table_name="position_sync_adjustment",
    )
    op.drop_column("position_sync_adjustment", "idempotency_key")
    op.drop_column("position_sync_adjustment", "reason")
    op.drop_column("position_sync_adjustment", "cost_basis_source")
    # 독립 adjustment는 execution 참조가 없으므로 downgrade 전에 정리 없이는
    # NOT NULL로 되돌릴 수 없습니다. 운영 데이터 손실을 피하기 위해 nullable을 유지합니다.

"""disable removed supported markets

Revision ID: 1c7e4a9b2d30
Revises: 4b9d7e2f1a60
Create Date: 2026-07-24 00:00:00
"""

from typing import Sequence, Union

from alembic import op


revision: str = "1c7e4a9b2d30"
down_revision: Union[str, None] = "4b9d7e2f1a60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REMOVED_MARKETS = ("KRW-ADA", "KRW-AVAX", "KRW-LINK", "KRW-DOT")


def upgrade() -> None:
    placeholders = ", ".join(f"'{market}'" for market in REMOVED_MARKETS)
    op.execute(
        f"UPDATE supported_market SET enabled = false WHERE code IN ({placeholders})"
    )


def downgrade() -> None:
    placeholders = ", ".join(f"'{market}'" for market in REMOVED_MARKETS)
    op.execute(
        f"UPDATE supported_market SET enabled = true WHERE code IN ({placeholders})"
    )

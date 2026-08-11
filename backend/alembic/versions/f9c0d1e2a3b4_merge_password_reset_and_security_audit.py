"""merge password reset and security audit heads

Revision ID: f9c0d1e2a3b4
Revises: e7b8c9d0a1f2, e8a1b2c3d4e5
"""

from typing import Sequence, Union


revision: str = "f9c0d1e2a3b4"
down_revision: Union[str, tuple[str, str], None] = (
    "e7b8c9d0a1f2",
    "e8a1b2c3d4e5",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

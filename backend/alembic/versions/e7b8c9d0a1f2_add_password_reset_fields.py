"""add password reset fields

Revision ID: e7b8c9d0a1f2
Revises: a1f2c3d4e5b6
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e7b8c9d0a1f2"
down_revision: Union[str, None] = "a1f2c3d4e5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("password_reset_token_hash", sa.String(length=64), nullable=True))
    op.add_column("user", sa.Column("password_reset_expires_at", sa.DateTime(), nullable=True))
    op.add_column("user", sa.Column("password_reset_attempts", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("user", "password_reset_attempts")
    op.drop_column("user", "password_reset_expires_at")
    op.drop_column("user", "password_reset_token_hash")

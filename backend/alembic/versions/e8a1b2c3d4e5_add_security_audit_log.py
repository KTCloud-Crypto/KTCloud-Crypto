"""add security audit log

Revision ID: e8a1b2c3d4e5
Revises: a1f2c3d4e5b6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8a1b2c3d4e5"
down_revision: Union[str, None] = "a1f2c3d4e5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "security_audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_key", sa.String(length=255), nullable=True),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_security_audit_log_event_type", "security_audit_log", ["event_type"])
    op.create_index("ix_security_audit_created_event", "security_audit_log", ["created_at", "event_type"])
    op.create_index("ix_security_audit_actor_created", "security_audit_log", ["actor_user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_security_audit_actor_created", table_name="security_audit_log")
    op.drop_index("ix_security_audit_created_event", table_name="security_audit_log")
    op.drop_index("ix_security_audit_log_event_type", table_name="security_audit_log")
    op.drop_table("security_audit_log")

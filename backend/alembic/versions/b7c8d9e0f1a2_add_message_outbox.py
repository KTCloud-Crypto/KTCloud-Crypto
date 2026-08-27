"""add message outbox

Revision ID: b7c8d9e0f1a2
Revises: e6a7b8c9d0e1
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "e6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "message_outbox",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.String(length=36), nullable=False),
        sa.Column("message_type", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("producer", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("transport_message_id", sa.String(length=128), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("message_id"),
    )
    op.create_index(
        "ix_message_outbox_message_type",
        "message_outbox",
        ["message_type"],
    )
    op.create_index(
        "ix_message_outbox_correlation_id",
        "message_outbox",
        ["correlation_id"],
    )
    op.create_index(
        "ix_message_outbox_pending",
        "message_outbox",
        ["status", "next_attempt_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_message_outbox_pending", table_name="message_outbox")
    op.drop_index("ix_message_outbox_correlation_id", table_name="message_outbox")
    op.drop_index("ix_message_outbox_message_type", table_name="message_outbox")
    op.drop_table("message_outbox")

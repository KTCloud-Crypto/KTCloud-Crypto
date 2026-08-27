from __future__ import annotations

from datetime import timezone

from sqlalchemy import Column, DateTime, Index, Integer, JSON, String, Text, func

from app.core.database import Base
from app.messaging.envelope import MessageEnvelope


class MessageOutbox(Base):
    """DB 변경과 같은 transaction에서 기록하는 미발행 메시지 원장입니다."""

    __tablename__ = "message_outbox"
    __table_args__ = (
        Index(
            "ix_message_outbox_pending",
            "status",
            "next_attempt_at",
            "created_at",
        ),
    )

    id = Column(Integer, primary_key=True)
    message_id = Column(String(36), nullable=False, unique=True)
    message_type = Column(String(128), nullable=False, index=True)
    correlation_id = Column(String(128), nullable=False, index=True)
    producer = Column(String(64), nullable=False)
    schema_version = Column(Integer, nullable=False, default=1)
    idempotency_key = Column(String(255), nullable=True, unique=True)
    payload = Column(JSON, nullable=False, default=dict)
    occurred_at = Column(DateTime(timezone=True), nullable=False)

    status = Column(String(16), nullable=False, default="pending")
    attempt_count = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_error = Column(Text, nullable=True)
    transport_message_id = Column(String(128), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    @classmethod
    def from_envelope(cls, envelope: MessageEnvelope) -> "MessageOutbox":
        return cls(
            message_id=str(envelope.message_id),
            message_type=envelope.message_type,
            correlation_id=envelope.correlation_id,
            producer=envelope.producer,
            schema_version=envelope.schema_version,
            idempotency_key=envelope.idempotency_key,
            payload=envelope.payload,
            occurred_at=envelope.occurred_at,
        )

    def to_envelope(self) -> MessageEnvelope:
        occurred_at = self.occurred_at
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        return MessageEnvelope(
            message_id=self.message_id,
            message_type=self.message_type,
            occurred_at=occurred_at,
            correlation_id=self.correlation_id,
            producer=self.producer,
            schema_version=self.schema_version,
            idempotency_key=self.idempotency_key,
            payload=self.payload,
        )

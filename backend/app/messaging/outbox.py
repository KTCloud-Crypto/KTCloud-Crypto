from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from sqlalchemy.orm import Session

from app.messaging.envelope import MessageEnvelope
from app.models.message_outbox import MessageOutbox


class QueuePublisher(Protocol):
    def publish(self, envelope: MessageEnvelope, *, delay_seconds: int = 0) -> str: ...


@dataclass(frozen=True)
class OutboxPublishResult:
    selected: int
    published: int
    failed: int


def enqueue_outbox(db: Session, envelope: MessageEnvelope) -> MessageOutbox:
    """호출자의 업무 DB 변경과 같은 transaction에 메시지를 추가합니다."""

    message = MessageOutbox.from_envelope(envelope)
    db.add(message)
    db.flush()
    return message


class OutboxPublisher:
    """미발행 Outbox 행을 SQS로 전달하고 결과를 같은 DB session에 기록합니다."""

    def __init__(self, queue: QueuePublisher, *, max_retry_seconds: int = 300) -> None:
        self._queue = queue
        self._max_retry_seconds = max_retry_seconds

    def publish_pending(
        self,
        db: Session,
        *,
        limit: int = 100,
        now: datetime | None = None,
    ) -> OutboxPublishResult:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        current_time = now or datetime.now(timezone.utc)
        pending = (
            db.query(MessageOutbox)
            .filter(
                MessageOutbox.status == "pending",
                MessageOutbox.next_attempt_at <= current_time,
            )
            .order_by(MessageOutbox.created_at, MessageOutbox.id)
            .with_for_update(skip_locked=True)
            .limit(limit)
            .all()
        )

        published = 0
        failed = 0
        for message in pending:
            message.attempt_count += 1
            try:
                transport_message_id = self._queue.publish(message.to_envelope())
            except Exception as exc:  # 발행 실패는 원장에 남기고 다음 주기에 재시도합니다.
                failed += 1
                retry_seconds = min(
                    2 ** min(message.attempt_count, 8),
                    self._max_retry_seconds,
                )
                message.next_attempt_at = current_time + timedelta(seconds=retry_seconds)
                message.last_error = str(exc)[:2000]
            else:
                published += 1
                message.status = "published"
                message.transport_message_id = transport_message_id
                message.published_at = current_time
                message.last_error = None

        db.flush()
        return OutboxPublishResult(
            selected=len(pending),
            published=published,
            failed=failed,
        )

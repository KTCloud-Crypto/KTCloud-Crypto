from __future__ import annotations

from app.messaging.envelope import MessageEnvelope
from app.messaging.outbox import enqueue_outbox


def enqueue_notification_requested(
    db,
    *,
    chat_id: str | None,
    message: str,
    producer: str,
    notification_type: str,
    user_id: int | None = None,
    idempotency_key: str | None = None,
) -> bool:
    """Producer transaction에 Telegram 전달 요청을 함께 기록합니다."""
    if not chat_id:
        return False
    enqueue_outbox(
        db,
        MessageEnvelope.create(
            message_type="NotificationRequested",
            producer=producer,
            idempotency_key=idempotency_key,
            payload={
                "chat_id": str(chat_id),
                "message": message,
                "notification_type": notification_type,
                "user_id": user_id,
            },
        ),
    )
    return True

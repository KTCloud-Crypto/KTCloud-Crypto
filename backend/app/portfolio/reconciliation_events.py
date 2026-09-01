from __future__ import annotations

from sqlalchemy.orm import Session

from app.messaging.envelope import MessageEnvelope
from app.messaging.outbox import enqueue_outbox
from app.models.message_outbox import MessageOutbox
from app.models.position_sync import PositionSyncAdjustment


def enqueue_position_reconciled(
    db: Session,
    adjustment: PositionSyncAdjustment,
) -> MessageOutbox:
    """Portfolio 차감과 같은 transaction에 Trading 정리 이벤트를 기록합니다."""
    db.flush()
    if adjustment.id is None:
        raise ValueError("PositionSyncAdjustment must be persisted before reconciliation event")

    key = f"position-adjustment:{adjustment.id}"
    return enqueue_outbox(
        db,
        MessageEnvelope.create(
            message_type="PositionReconciled",
            producer="portfolio",
            correlation_id=key,
            idempotency_key=key,
            payload={
                "adjustment_id": adjustment.id,
                "user_strategy_id": adjustment.user_strategy_id,
            },
        ),
    )

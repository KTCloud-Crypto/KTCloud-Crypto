from __future__ import annotations

from sqlalchemy.orm import Session

from app.messaging.envelope import MessageEnvelope
from app.messaging.outbox import enqueue_outbox
from app.models.message_outbox import MessageOutbox
from app.models.strategy_signal import StrategyExecution


def enqueue_allocation_changed(
    db: Session,
    execution: StrategyExecution,
    *,
    allocated_amount: float,
) -> MessageOutbox:
    """확정 체결 결과를 Strategy 소유 예산에 반영하도록 이벤트로 전달합니다."""
    db.flush()
    if execution.id is None:
        raise ValueError("StrategyExecution must be persisted before allocation event")

    key = f"execution-allocation:{execution.id}"
    return enqueue_outbox(
        db,
        MessageEnvelope.create(
            message_type="AllocationChanged",
            producer="trading",
            correlation_id=key,
            idempotency_key=key,
            payload={
                "execution_id": execution.id,
                "user_strategy_id": execution.user_strategy_id,
                "allocated_amount": allocated_amount,
            },
        ),
    )

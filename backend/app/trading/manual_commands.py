from __future__ import annotations

from app.messaging.envelope import MessageEnvelope
from app.messaging.outbox import enqueue_outbox
from app.models.strategy_signal import TradingExecutionRequest


def enqueue_manual_liquidation(db, request: TradingExecutionRequest) -> None:
    db.flush()
    enqueue_outbox(
        db,
        MessageEnvelope.create(
            message_type="ManualLiquidationRequested",
            producer="trading-api",
            correlation_id=f"manual-liquidation:{request.id}",
            idempotency_key=f"manual-liquidation:{request.id}",
            payload={"execution_request_id": request.id},
        ),
    )

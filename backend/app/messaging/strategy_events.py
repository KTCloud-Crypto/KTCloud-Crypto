from __future__ import annotations

from sqlalchemy.orm import Session

from app.messaging.envelope import MessageEnvelope
from app.messaging.outbox import enqueue_outbox
from app.models.message_outbox import MessageOutbox
from app.models.strategy_signal import StrategySignal


def enqueue_strategy_signal_created(
    db: Session,
    signal: StrategySignal,
    *,
    target_user_id: int | None = None,
    target_mode: str | None = None,
) -> MessageOutbox:
    """StrategySignal과 같은 transaction에 생성 이벤트를 기록합니다."""

    # signal_id를 이벤트의 안정적인 식별자로 사용하기 위해 먼저 flush합니다.
    # commit은 호출자가 담당하므로 Signal과 Outbox는 함께 성공하거나 롤백됩니다.
    db.flush()
    if signal.id is None:
        raise ValueError("StrategySignal must have an id before creating its event")

    signal_key = f"strategy-signal:{signal.id}"
    envelope = MessageEnvelope.create(
        message_type="StrategySignalCreated",
        producer="strategy",
        correlation_id=signal_key,
        idempotency_key=signal_key,
        payload={
            "signal_id": signal.id,
            "strategy_id": signal.strategy_id,
            "market": signal.market,
            "timeframe_minutes": signal.timeframe_minutes,
            "action": signal.action,
            "source": signal.source,
            "candle_open_time": signal.candle_open_time.isoformat(),
            "close_price": signal.close_price,
            "metrics": signal.metrics or {},
            "target_user_id": target_user_id,
            "target_mode": target_mode,
        },
    )
    return enqueue_outbox(db, envelope)

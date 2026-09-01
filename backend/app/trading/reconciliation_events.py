from __future__ import annotations

from app.core.database import SessionLocal
from app.messaging.envelope import MessageEnvelope
from app.models.strategy_signal import StrategyExecution


def apply_position_reconciled(envelope: MessageEnvelope) -> int:
    """Portfolio 정리 결과를 Trading 소유의 미확정 실행에 반영합니다."""
    if envelope.message_type != "PositionReconciled":
        raise ValueError(f"unsupported reconciliation event: {envelope.message_type}")
    user_strategy_id = envelope.payload.get("user_strategy_id")
    if not isinstance(user_strategy_id, int) or user_strategy_id <= 0:
        raise ValueError("PositionReconciled.user_strategy_id must be a positive integer")

    with SessionLocal() as db:
        executions = (
            db.query(StrategyExecution)
            .filter(
                StrategyExecution.user_strategy_id == user_strategy_id,
                StrategyExecution.action == "sell",
                StrategyExecution.status == "uncertain",
            )
            .all()
        )
        for execution in executions:
            execution.status = "reconciled"
            execution.error_message = "실제 잔고 차이를 사용자가 전략 포지션에 반영했습니다."
        db.commit()
        return len(executions)

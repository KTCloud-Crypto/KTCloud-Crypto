from __future__ import annotations

from dataclasses import dataclass

from app.core.database import SessionLocal
from app.messaging.envelope import MessageEnvelope
from app.models.strategy import UserStrategy


@dataclass(frozen=True, slots=True)
class AllocationChangedResult:
    execution_id: int
    user_strategy_id: int
    updated: bool


def apply_allocation_changed(envelope: MessageEnvelope) -> AllocationChangedResult:
    """Trading의 확정 체결 예산을 Strategy 소유 구독에 idempotent하게 반영합니다."""
    if envelope.message_type != "AllocationChanged":
        raise ValueError(f"unsupported strategy message type: {envelope.message_type}")
    execution_id = envelope.payload.get("execution_id")
    user_strategy_id = envelope.payload.get("user_strategy_id")
    allocated_amount = envelope.payload.get("allocated_amount")
    if not isinstance(execution_id, int) or execution_id <= 0:
        raise ValueError("AllocationChanged.execution_id must be a positive integer")
    if not isinstance(user_strategy_id, int) or user_strategy_id <= 0:
        raise ValueError("AllocationChanged.user_strategy_id must be a positive integer")
    if not isinstance(allocated_amount, (int, float)) or allocated_amount < 0:
        raise ValueError("AllocationChanged.allocated_amount must be a non-negative number")

    with SessionLocal() as db:
        subscription = db.get(UserStrategy, user_strategy_id)
        if subscription is None:
            return AllocationChangedResult(execution_id, user_strategy_id, False)
        subscription.allocated_amount = float(allocated_amount)
        db.commit()
    return AllocationChangedResult(execution_id, user_strategy_id, True)

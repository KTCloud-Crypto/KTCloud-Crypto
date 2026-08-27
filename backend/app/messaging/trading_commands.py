from __future__ import annotations

from dataclasses import dataclass

from app.messaging.envelope import MessageEnvelope
from app.trading.signal_dispatcher import dispatch_signal


@dataclass(frozen=True, slots=True)
class TradingCommandResult:
    """Trading consumer가 처리한 전략 신호의 결과입니다."""

    signal_id: int
    target_user_id: int | None
    target_mode: str | None
    execution_count: int


def _validated_scope(envelope: MessageEnvelope) -> tuple[int, int | None, str | None]:
    if envelope.message_type != "StrategySignalCreated":
        raise ValueError(f"unsupported trading message type: {envelope.message_type}")

    signal_id = envelope.payload.get("signal_id")
    if not isinstance(signal_id, int) or signal_id <= 0:
        raise ValueError("StrategySignalCreated.signal_id must be a positive integer")

    target_user_id = envelope.payload.get("target_user_id")
    if target_user_id is not None and (
        not isinstance(target_user_id, int) or target_user_id <= 0
    ):
        raise ValueError("target_user_id must be a positive integer or null")

    target_mode = envelope.payload.get("target_mode")
    if target_mode not in {None, "simulated", "live"}:
        raise ValueError("target_mode must be simulated, live, or null")

    return signal_id, target_user_id, target_mode


async def execute_strategy_signal(envelope: MessageEnvelope) -> TradingCommandResult:
    """Queue에서 받은 신호를 실제 모의·실전 주문 실행 경로로 전달합니다.

    SQS는 at-least-once 방식이므로 같은 메시지가 다시 올 수 있습니다.
    중복 실행 방지는 dispatcher가 생성하는 StrategyExecution의
    ``(signal_id, user_strategy_id)`` 유일 제약으로 보장합니다.
    """

    signal_id, target_user_id, target_mode = _validated_scope(envelope)
    execution_count = await dispatch_signal(
        signal_id,
        user_id=target_user_id,
        mode=target_mode,
    )
    return TradingCommandResult(
        signal_id=signal_id,
        target_user_id=target_user_id,
        target_mode=target_mode,
        execution_count=execution_count,
    )

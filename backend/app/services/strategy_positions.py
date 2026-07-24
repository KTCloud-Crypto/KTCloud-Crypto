"""전략 실행 기록으로 현재 전략 소유 수량과 평균 매수가를 계산합니다."""

from dataclasses import dataclass

from app.models.strategy_signal import StrategyExecution


@dataclass(frozen=True, slots=True)
class CalculatedPosition:
    volume: float
    average_buy_price: float | None


def calculate_position(
    executions: list[StrategyExecution],
    success_statuses: frozenset[str] = frozenset({"success"}),
) -> CalculatedPosition:
    """성공 체결을 시간순으로 반영하며 부분 매도 후에도 원가를 유지합니다."""
    volume = 0.0
    cost = 0.0
    for execution in sorted(executions, key=lambda item: (item.created_at, item.id)):
        if execution.status not in success_statuses or not execution.executed_volume:
            continue
        executed_volume = float(execution.executed_volume)
        if execution.action == "buy":
            price = float(execution.average_price or execution.price)
            volume += executed_volume
            cost += executed_volume * price
        elif execution.action == "sell" and volume > 0:
            sold = min(executed_volume, volume)
            average_price = cost / volume
            volume -= sold
            cost = max(0.0, cost - sold * average_price)

    if volume <= 1e-12:
        return CalculatedPosition(0.0, None)
    return CalculatedPosition(volume, cost / volume)

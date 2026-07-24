"""전략 체결 기록을 매입·매도 금액과 확정 손익 정보로 보강합니다."""

from dataclasses import dataclass

from app.models.strategy_signal import StrategyExecution

DEFAULT_FEE_RATE = 0.0005


@dataclass(frozen=True, slots=True)
class ExecutionTradeDetail:
    entry_price: float | None
    transaction_amount: float | None
    realized_profit_loss: float | None


def execution_trade_details(
    executions: list[StrategyExecution],
    fee_rate: float = DEFAULT_FEE_RATE,
) -> dict[int, ExecutionTradeDetail]:
    """전략별 평균원가를 추적해 수수료 반영 거래 정보를 반환합니다."""
    positions: dict[int, tuple[float, float]] = {}
    result: dict[int, ExecutionTradeDetail] = {}

    for execution in sorted(executions, key=lambda item: (item.created_at, item.id)):
        success_statuses = (
            {"simulated_success"} if execution.mode == "simulated"
            else {"success", "partially_filled"}
        )
        if (
            execution.status not in success_statuses
            or not execution.executed_volume
        ):
            result[execution.id] = ExecutionTradeDetail(None, None, None)
            continue

        volume = float(execution.executed_volume)
        price = float(execution.average_price or execution.price)
        transaction_amount = volume * price
        position_volume, position_cost = positions.get(execution.user_strategy_id, (0.0, 0.0))

        if execution.action == "buy":
            positions[execution.user_strategy_id] = (
                position_volume + volume,
                position_cost + transaction_amount,
            )
            result[execution.id] = ExecutionTradeDetail(
                entry_price=price,
                transaction_amount=transaction_amount,
                realized_profit_loss=None,
            )
            continue

        if execution.action == "sell" and position_volume > 0:
            sold_volume = min(volume, position_volume)
            average_entry_price = position_cost / position_volume
            matched_cost = sold_volume * average_entry_price
            positions[execution.user_strategy_id] = (
                position_volume - sold_volume,
                max(0.0, position_cost - matched_cost),
            )
            result[execution.id] = ExecutionTradeDetail(
                entry_price=average_entry_price,
                transaction_amount=transaction_amount,
                realized_profit_loss=(
                    price * sold_volume * (1 - fee_rate)
                    - average_entry_price * sold_volume * (1 + fee_rate)
                ),
            )
            continue

        result[execution.id] = ExecutionTradeDetail(
            entry_price=None,
            transaction_amount=transaction_amount,
            realized_profit_loss=None,
        )

    return result

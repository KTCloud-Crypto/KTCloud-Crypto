"""실전 전략 체결 기록에서 확정 손익을 계산합니다."""

from dataclasses import dataclass

from app.models.strategy_signal import StrategyExecution

DEFAULT_FEE_RATE = 0.0005


@dataclass(frozen=True, slots=True)
class RealizedProfit:
    profit_loss: float
    sold_cost_basis: float


def calculate_realized_profit(
    executions: list[StrategyExecution],
    fee_rate: float = DEFAULT_FEE_RATE,
) -> RealizedProfit:
    """평균원가법으로 매도된 수량의 확정 손익과 원가를 계산합니다.

    현재 체결 테이블에는 거래소가 반환한 실제 수수료가 없으므로 업비트의
    기본 수수료율을 매수·매도 양쪽에 적용합니다.
    """
    volume = 0.0
    cost_including_buy_fee = 0.0
    realized = 0.0
    sold_cost_basis = 0.0

    for execution in sorted(executions, key=lambda item: (item.created_at, item.id)):
        if execution.status != "success" or not execution.executed_volume:
            continue

        executed_volume = float(execution.executed_volume)
        price = float(execution.average_price or execution.price)
        if execution.action == "buy":
            gross_cost = executed_volume * price
            paid_fee = getattr(execution, "paid_fee", None)
            buy_fee = float(paid_fee) if paid_fee is not None else gross_cost * fee_rate
            volume += executed_volume
            cost_including_buy_fee += gross_cost + buy_fee
            continue

        if execution.action != "sell" or volume <= 0:
            continue

        sold_volume = min(executed_volume, volume)
        average_cost = cost_including_buy_fee / volume
        matched_cost = sold_volume * average_cost
        paid_fee = getattr(execution, "paid_fee", None)
        sell_fee = (
            float(paid_fee) * (sold_volume / executed_volume)
            if paid_fee is not None
            else sold_volume * price * fee_rate
        )
        net_proceeds = sold_volume * price - sell_fee

        realized += net_proceeds - matched_cost
        sold_cost_basis += matched_cost
        volume -= sold_volume
        cost_including_buy_fee = max(0.0, cost_including_buy_fee - matched_cost)

    return RealizedProfit(
        profit_loss=realized,
        sold_cost_basis=sold_cost_basis,
    )

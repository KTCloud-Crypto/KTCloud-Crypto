from typing import Literal

from pydantic import BaseModel, Field


class UpbitBalanceOut(BaseModel):
    """업비트 실계좌 잔고 응답 스키마"""

    currency: str
    balance: float
    locked: float
    avg_buy_price: float


class LiveAccountSummaryOut(BaseModel):
    """실전 체결의 확정 손익과 현재 보유 코인의 평가손익."""

    purchase_amount: float
    evaluation_amount: float
    realized_profit_loss: float
    unrealized_profit_loss: float
    profit_loss: float
    return_rate: float | None


class PortfolioAllocationOut(BaseModel):
    """포트폴리오 배정 현황"""

    strategy_id: int
    strategy_name: str
    market: str
    invest_ratio: float
    allocation_amount: float
    current_position_value: float
    enabled: bool


class PortfolioSummaryOut(BaseModel):
    """실전투자 포트폴리오 전체 현황"""

    available_krw: float
    managed_positions_value: float
    total_equity: float
    strategies: list[PortfolioAllocationOut]


class ReconciliationStrategyOut(BaseModel):
    strategy_id: int
    subscription_id: int
    strategy_name: str
    market: str
    volume: float


class PositionReconciliationOut(BaseModel):
    """Upbit 실제 수량과 자동매매 전략 기록 수량의 비교 결과."""

    currency: str
    actual_available: float
    actual_locked: float
    actual_total: float
    strategy_volume: float
    difference: float
    status: str
    message: str
    strategies: list[ReconciliationStrategyOut]


class PositionSyncIn(BaseModel):
    subscription_id: int
    action: Literal["buy", "sell"]
    volume: float = Field(gt=0)

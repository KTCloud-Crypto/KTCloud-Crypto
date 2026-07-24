from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class StrategyOut(BaseModel):
    id: int
    code: str
    name: str
    description: str
    market: str
    market_name: str
    timeframe_minutes: int
    parameters: dict[str, float | int]
    default_invest_ratio: float
    selected: bool
    paused: bool
    has_open_position: bool
    invest_ratio: float
    stop_loss_rate: float | None
    take_profit_rate: float | None
    selected_timeframe_minutes: int
    allowed_timeframes: list[int]
    last_evaluated_at: datetime | None = None
    last_close_price: float | None = None
    last_metrics: dict[str, float] = Field(default_factory=dict)
    last_action: str | None = None


class StrategySubscriptionIn(BaseModel):
    enabled: bool
    force_disable: bool = False
    invest_ratio: float | None = Field(default=None, ge=0.01, le=1.0)
    timeframe_minutes: Literal[1, 3, 5, 10, 30, 60, 240] | None = None
    stop_loss_rate: float | None = Field(default=None, ge=0, le=1.0)
    take_profit_rate: float | None = Field(default=None, ge=0, le=1.0)


class SupportedMarketOut(BaseModel):
    code: str
    display_name: str


class StrategyTestSignalIn(BaseModel):
    action: Literal["buy", "sell"]


class StrategyTestSignalOut(BaseModel):
    signal_id: int
    execution_count: int
    action: str
    market: str
    price: float


class StrategySignalOut(BaseModel):
    id: int
    strategy_name: str
    strategy_code: str
    market: str
    timeframe_minutes: int
    action: Literal["buy", "sell"]
    source: str
    close_price: float
    metrics: dict[str, float]
    candle_open_time: datetime
    created_at: datetime


class StrategyPositionOut(BaseModel):
    strategy_id: int
    strategy_name: str
    strategy_code: str
    market: str
    enabled: bool
    timeframe_minutes: int
    invest_ratio: float
    volume: float
    average_buy_price: float | None
    status: Literal["holding", "flat"]
    paper_volume: float
    paper_average_buy_price: float | None
    paper_status: Literal["holding", "flat"]


class StrategyExecutionOut(BaseModel):
    id: int
    strategy_name: str
    strategy_code: str
    action: Literal["buy", "sell"]
    market: str
    mode: Literal["simulated", "live"]
    status: str
    price: float
    order_amount: float | None
    order_volume: float | None
    executed_volume: float | None
    average_price: float | None
    entry_price: float | None
    transaction_amount: float | None
    realized_profit_loss: float | None
    error_message: str | None
    notification_sent: bool
    exit_reason: str | None
    created_at: datetime

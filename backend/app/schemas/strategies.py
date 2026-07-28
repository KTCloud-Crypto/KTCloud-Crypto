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
    # 구독 시점에 확정된 주문 예산입니다. 매도하면 회수 금액으로 갱신됩니다.
    allocated_amount: float | None = None
    # 다른 전략이 확보한 예산을 뺀 주문 가능 현금입니다. 금액 입력 상한 안내용입니다.
    available_cash: float | None = None
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
    # 비율 대신 주문 금액을 직접 지정할 때 사용합니다. 서버에서 최소 주문 금액과
    # 주문 가능 현금을 검사한 뒤 그대로 주문 예산으로 확정합니다.
    invest_amount: float | None = Field(default=None, ge=0)
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
 
from datetime import date

from pydantic import BaseModel


class AnalyticsMetric(BaseModel):
    realized_pnl: float
    total_fee: float
    trade_count: int
    sell_count: int
    win_count: int
    win_rate: float
    buy_amount: float
    sell_amount: float


class DailyPnlPoint(BaseModel):
    date: date
    pnl: float
    cumulative_pnl: float


class TickerPerformance(BaseModel):
    ticker: str
    buy_amount: float
    sell_amount: float
    realized_pnl: float
    trade_count: int
    weight: float


class AnalyticsOut(BaseModel):
    all_time: AnalyticsMetric
    today: AnalyticsMetric
    week: AnalyticsMetric
    month: AnalyticsMetric
    daily_pnl: list[DailyPnlPoint]
    tickers: list[TickerPerformance]
    excluded_trade_count: int
    fee_included: bool = False

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.trade import Trade
from app.models.strategy_signal import StrategyExecution
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsMetric,
    AnalyticsOut,
    DailyPnlPoint,
    TickerPerformance,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@dataclass
class AnalyzedTrade:
    ticker: str
    action: str
    amount: float
    pnl: float
    created_at: datetime


@dataclass
class AnalysisSourceTrade:
    id: int
    ticker: str
    action: str
    price: float | None
    volume: float | None
    status: str
    created_at: datetime


def analyze_trades(trades: list[Trade]) -> tuple[list[AnalyzedTrade], int]:
    """체결 거래를 FIFO 방식으로 매칭하여 실현손익을 계산합니다."""
    lots: dict[str, deque[list[float]]] = defaultdict(deque)
    analyzed: list[AnalyzedTrade] = []
    excluded = 0

    for trade in sorted(trades, key=lambda item: (item.created_at, item.id or 0)):
        volume = trade.volume
        if trade.status != "success" or not trade.price or not volume or volume <= 0:
            excluded += 1
            continue

        price = float(trade.price)
        volume = float(volume)
        amount = price * volume
        pnl = 0.0

        if trade.action == "buy":
            lots[trade.ticker].append([volume, price])
        elif trade.action == "sell":
            remaining = volume
            while remaining > 0 and lots[trade.ticker]:
                lot = lots[trade.ticker][0]
                matched = min(remaining, lot[0])
                pnl += (price - lot[1]) * matched
                remaining -= matched
                lot[0] -= matched
                if lot[0] <= 1e-12:
                    lots[trade.ticker].popleft()
        else:
            excluded += 1
            continue

        analyzed.append(AnalyzedTrade(trade.ticker, trade.action, amount, pnl, trade.created_at))

    return analyzed, excluded


def build_metric(trades: list[AnalyzedTrade], start: datetime | None = None) -> AnalyticsMetric:
    selected = [trade for trade in trades if start is None or trade.created_at >= start]
    sells = [trade for trade in selected if trade.action == "sell"]
    wins = sum(1 for trade in sells if trade.pnl > 0)
    return AnalyticsMetric(
        realized_pnl=round(sum(trade.pnl for trade in sells), 4),
        trade_count=len(selected),
        sell_count=len(sells),
        win_count=wins,
        win_rate=round(wins / len(sells) * 100, 2) if sells else 0,
        buy_amount=round(sum(trade.amount for trade in selected if trade.action == "buy"), 4),
        sell_amount=round(sum(trade.amount for trade in sells), 4),
    )


@router.get("", response_model=AnalyticsOut)
def get_analytics(
    mode: Literal["live", "simulated"] = Query(default="live"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalyticsOut:
    if mode == "simulated":
        executions = (
            db.query(StrategyExecution)
            .filter(
                StrategyExecution.user_id == current_user.id,
                StrategyExecution.mode == "simulated",
            )
            .order_by(StrategyExecution.created_at.asc())
            .all()
        )
        raw_trades = [
            AnalysisSourceTrade(
                id=execution.id,
                ticker=execution.market,
                action=execution.action,
                price=execution.average_price or execution.price,
                volume=execution.executed_volume or execution.order_volume,
                status="success" if execution.status == "simulated_success" else execution.status,
                created_at=execution.created_at,
            )
            for execution in executions
        ]
    else:
        raw_trades = (
            db.query(Trade)
            .filter(Trade.user_id == current_user.id)
            .order_by(Trade.created_at.asc())
            .all()
        )
    trades, excluded = analyze_trades(raw_trades)
    now = datetime.utcnow()
    today_start = datetime.combine(now.date(), datetime.min.time())
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    pnl_by_date: dict[date, float] = defaultdict(float)
    for trade in trades:
        if trade.action == "sell":
            pnl_by_date[trade.created_at.date()] += trade.pnl
    cumulative = sum(value for day, value in pnl_by_date.items() if day < now.date() - timedelta(days=29))
    daily_points = []
    for offset in range(29, -1, -1):
        day = now.date() - timedelta(days=offset)
        pnl = pnl_by_date.get(day, 0.0)
        cumulative += pnl
        daily_points.append(DailyPnlPoint(date=day, pnl=round(pnl, 4), cumulative_pnl=round(cumulative, 4)))

    ticker_values: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for trade in trades:
        values = ticker_values[trade.ticker]
        values[f"{trade.action}_amount"] += trade.amount
        values["realized_pnl"] += trade.pnl
        values["trade_count"] += 1
    total_volume = sum(values["buy_amount"] + values["sell_amount"] for values in ticker_values.values())
    tickers = [
        TickerPerformance(
            ticker=ticker,
            buy_amount=round(values["buy_amount"], 4),
            sell_amount=round(values["sell_amount"], 4),
            realized_pnl=round(values["realized_pnl"], 4),
            trade_count=int(values["trade_count"]),
            weight=round((values["buy_amount"] + values["sell_amount"]) / total_volume * 100, 2) if total_volume else 0,
        )
        for ticker, values in ticker_values.items()
    ]
    tickers.sort(key=lambda item: item.buy_amount + item.sell_amount, reverse=True)

    return AnalyticsOut(
        all_time=build_metric(trades),
        today=build_metric(trades, today_start),
        week=build_metric(trades, week_start),
        month=build_metric(trades, month_start),
        daily_pnl=daily_points,
        tickers=tickers[:10],
        excluded_trade_count=excluded,
    )

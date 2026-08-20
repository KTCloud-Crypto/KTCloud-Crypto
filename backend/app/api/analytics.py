from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.strategy_signal import StrategyExecution, StrategySignal
from app.models.position_sync import PositionSyncAdjustment
from app.models.strategy import Strategy, UserStrategy, SupportedMarket
from app.models.user import User
from app.services.strategy_positions import DEFAULT_FEE_RATE
from app.schemas.analytics import (
    AnalyticsMetric,
    AnalyticsOut,
    DailyPnlPoint,
    TickerPerformance,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])
KST = timezone(timedelta(hours=9))


def _kst_date(value: datetime) -> date:
    """DB의 UTC 시각을 사용자가 보는 한국 날짜로 변환합니다."""
    utc_value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return utc_value.astimezone(KST).date()


def _utc_start_of_kst_day(day: date) -> datetime:
    """한국 날짜의 자정을 DB 비교용 UTC naive 시각으로 변환합니다."""
    local_start = datetime.combine(day, datetime.min.time(), tzinfo=KST)
    return local_start.astimezone(timezone.utc).replace(tzinfo=None)


@dataclass
class AnalyzedTrade:
    ticker: str
    action: str
    amount: float
    pnl: float
    fee: float
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
    position_key: int | None = None
    paid_fee: float | None = None
    event_type: str = "trade"


def analyze_trades(
    trades: list[AnalysisSourceTrade],
    fee_rate: float = DEFAULT_FEE_RATE,
) -> tuple[list[AnalyzedTrade], int]:
    """전략별 평균원가와 매수·매도 수수료로 실현손익을 계산합니다."""
    positions: dict[str | int, list[float]] = defaultdict(lambda: [0.0, 0.0])
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
        paid_fee = getattr(trade, "paid_fee", None)
        execution_fee = float(paid_fee) if paid_fee is not None else amount * fee_rate
        position_key = getattr(trade, "position_key", None)
        lot_key = position_key if position_key is not None else trade.ticker
        event_type = getattr(trade, "event_type", "trade")

        position = positions[lot_key]
        position_volume, position_cost = position

        if event_type == "deduct":
            if position_volume > 0:
                removed = min(volume, position_volume)
                average_cost = position_cost / position_volume
                position[0] = position_volume - removed
                position[1] = max(0.0, position_cost - removed * average_cost)
            continue
        if trade.action == "buy":
            position[0] = position_volume + volume
            position[1] = position_cost + amount + execution_fee
        elif trade.action == "sell":
            if position_volume > 0:
                sold = min(volume, position_volume)
                average_cost = position_cost / position_volume
                sold_cost = sold * average_cost
                sell_fee = execution_fee * (sold / volume)
                net_proceeds = sold * price - sell_fee
                pnl = net_proceeds - sold_cost
                position[0] = position_volume - sold
                position[1] = max(0.0, position_cost - sold_cost)
        else:
            excluded += 1
            continue

        analyzed.append(AnalyzedTrade(trade.ticker, trade.action, amount, pnl, execution_fee, trade.created_at))

    return analyzed, excluded


def build_metric(trades: list[AnalyzedTrade], start: datetime | None = None) -> AnalyticsMetric:
    selected = [trade for trade in trades if start is None or trade.created_at >= start]
    buys = [trade for trade in selected if trade.action == "buy"]
    sells = [trade for trade in selected if trade.action == "sell"]
    wins = sum(1 for trade in sells if trade.pnl > 0)
    return AnalyticsMetric(
        realized_pnl=round(sum(trade.pnl for trade in sells), 4),
        total_fee=round(sum(trade.fee for trade in selected), 4),
        trade_count=len(selected),
        sell_count=len(sells),
        win_count=wins,
        win_rate=round(wins / len(sells) * 100, 2) if sells else 0,
        buy_amount=round(sum(trade.amount for trade in buys), 4),
        sell_amount=round(sum(trade.amount for trade in sells), 4),
    )


def build_daily_pnl_points(trades: list[AnalyzedTrade], end_date: date) -> list[DailyPnlPoint]:
    """최근 30일의 일별 손익을 해당 기간의 0원부터 누적합니다."""
    pnl_by_date: dict[date, float] = defaultdict(float)
    for trade in trades:
        if trade.action == "sell":
            pnl_by_date[_kst_date(trade.created_at)] += trade.pnl

    cumulative = 0.0
    daily_points = []
    for offset in range(29, -1, -1):
        day = end_date - timedelta(days=offset)
        pnl = pnl_by_date.get(day, 0.0)
        cumulative += pnl
        daily_points.append(
            DailyPnlPoint(
                date=day,
                pnl=round(pnl, 4),
                cumulative_pnl=round(cumulative, 4),
            )
        )
    return daily_points


@router.get("", response_model=AnalyticsOut)
async def get_analytics(
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
                position_key=execution.user_strategy_id,
                paid_fee=execution.paid_fee,
            )
            for execution in executions
        ]
    else:
        executions = (
            db.query(StrategyExecution)
            .join(StrategySignal, StrategySignal.id == StrategyExecution.signal_id)
            .join(UserStrategy, UserStrategy.id == StrategyExecution.user_strategy_id)
            .join(Strategy, Strategy.id == UserStrategy.strategy_id)
            .filter(
                StrategyExecution.user_id == current_user.id,
                StrategyExecution.mode == "live",
                StrategySignal.source != "external_sync",
                Strategy.code != "manual_hold_v1",
            )
            .order_by(StrategyExecution.created_at.asc())
            .all()
        )
        # 외부 귀속 조정은 주문 통계가 아니므로 실제 StrategyExecution만 분석합니다.
        raw_trades = [
            AnalysisSourceTrade(
                id=execution.id,
                ticker=execution.market,
                action=execution.action,
                price=execution.average_price or execution.price,
                volume=execution.executed_volume or execution.order_volume,
                status=execution.status,
                created_at=execution.created_at,
                position_key=execution.user_strategy_id,
                paid_fee=execution.paid_fee,
            )
            for execution in executions
        ]
        adjustment_rows = (
            db.query(PositionSyncAdjustment, SupportedMarket.code)
            .join(UserStrategy, UserStrategy.id == PositionSyncAdjustment.user_strategy_id)
            .join(Strategy, Strategy.id == UserStrategy.strategy_id)
            .join(SupportedMarket, SupportedMarket.id == UserStrategy.market_id)
            .filter(
                PositionSyncAdjustment.user_id == current_user.id,
                PositionSyncAdjustment.action.in_(["deduct", "sell"]),
                Strategy.code != "manual_hold_v1",
            )
            .all()
        )
        raw_trades.extend(
            AnalysisSourceTrade(
                id=1_000_000_000 + adjustment.id,
                ticker=market,
                action="sell",
                price=adjustment.reference_price,
                volume=adjustment.volume,
                status="success",
                created_at=adjustment.created_at,
                position_key=adjustment.user_strategy_id,
                event_type="deduct",
            )
            for adjustment, market in adjustment_rows
        )
    trades, excluded = analyze_trades(raw_trades)
    now = datetime.utcnow()
    today = _kst_date(now)
    today_start = _utc_start_of_kst_day(today)
    week_start = _utc_start_of_kst_day(today - timedelta(days=today.weekday()))
    month_start = _utc_start_of_kst_day(today.replace(day=1))

    daily_points = build_daily_pnl_points(trades, today)

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
        fee_included=True,
    )

from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.analytics import (
    AnalyzedTrade,
    _kst_date,
    analyze_trades,
    build_daily_pnl_points,
    build_metric,
    performance_executions_query,
)


def trade(identifier: int, action: str, price: float, volume: float, minutes: int = 0):
    return SimpleNamespace(
        id=identifier,
        ticker="KRW-BTC",
        action=action,
        price=price,
        volume=volume,
        executed_volume=None,
        status="success",
        created_at=datetime(2026, 1, 1) + timedelta(minutes=minutes),
    )


def test_analytics_calculates_fifo_realized_profit() -> None:
    analyzed, excluded = analyze_trades([
        trade(1, "buy", 100, 2),
        trade(2, "buy", 200, 1, 1),
        trade(3, "sell", 250, 2.5, 2),
    ])

    metric = build_metric(analyzed)

    assert excluded == 0
    assert metric.realized_pnl == 325
    assert metric.win_rate == 100
    assert metric.buy_amount == 400
    assert metric.sell_amount == 625


def test_analytics_excludes_failed_or_incomplete_trade() -> None:
    failed = trade(1, "buy", 100, 1)
    failed.status = "failed"
    incomplete = trade(2, "buy", 100, 1)
    incomplete.volume = None

    analyzed, excluded = analyze_trades([failed, incomplete])

    assert analyzed == []
    assert excluded == 2


def test_daily_pnl_accumulates_losses_from_zero_within_30_day_window() -> None:
    end = datetime(2026, 2, 1)
    analyzed = [
        AnalyzedTrade("KRW-BTC", "sell", 100, 500, end - timedelta(days=30)),
        AnalyzedTrade("KRW-BTC", "sell", 100, -120, end - timedelta(days=2)),
        AnalyzedTrade("KRW-BTC", "sell", 100, 20, end),
    ]

    points = build_daily_pnl_points(analyzed, end.date())

    assert len(points) == 30
    assert points[0].cumulative_pnl == 0
    assert points[-3].cumulative_pnl == -120
    assert points[-1].cumulative_pnl == -100


def test_daily_pnl_groups_utc_trade_by_korean_calendar_date() -> None:
    # UTC 15시는 한국시간으로 다음 날 자정입니다.
    trade_time = datetime(2026, 1, 1, 15, 0)
    analyzed = [AnalyzedTrade("KRW-BTC", "sell", 100, 30, trade_time)]

    points = build_daily_pnl_points(analyzed, datetime(2026, 1, 2).date())

    assert _kst_date(trade_time) == datetime(2026, 1, 2).date()
    assert points[-1].date == datetime(2026, 1, 2).date()
    assert points[-1].pnl == 30


def test_daily_and_cumulative_pnl_use_fifo_and_korean_dates() -> None:
    # 원가가 되는 매수는 30일 범위 밖이어도 FIFO 계산에는 포함되어야 합니다.
    buy = trade(1, "buy", 100, 2)
    buy.created_at = datetime(2025, 11, 1)
    first_sell = trade(2, "sell", 80, 0.5)
    first_sell.created_at = datetime(2026, 1, 1, 14, 59)  # KST 1/1 23:59
    second_sell = trade(3, "sell", 120, 0.5)
    second_sell.created_at = datetime(2026, 1, 1, 15, 0)  # KST 1/2 00:00
    third_sell = trade(4, "sell", 150, 1)
    third_sell.created_at = datetime(2026, 1, 2, 1, 0)  # KST 1/2 10:00

    analyzed, excluded = analyze_trades([buy, first_sell, second_sell, third_sell])
    points = build_daily_pnl_points(analyzed, datetime(2026, 1, 2).date())

    assert excluded == 0
    assert points[-2].date == datetime(2026, 1, 1).date()
    assert points[-2].pnl == -10
    assert points[-2].cumulative_pnl == -10
    assert points[-1].date == datetime(2026, 1, 2).date()
    assert points[-1].pnl == 60
    assert points[-1].cumulative_pnl == 50


def test_performance_query_can_exclude_manual_hold_strategy() -> None:
    """성과 집계 쿼리는 미배정 자산 전략을 명시적으로 제외해야 합니다."""
    db = sessionmaker(bind=create_engine("sqlite://"))()
    try:
        sql = str(performance_executions_query(db, 1).statement.compile(compile_kwargs={"literal_binds": True}))
    finally:
        db.close()
    assert "strategy.code != 'manual_hold_v1'" in sql

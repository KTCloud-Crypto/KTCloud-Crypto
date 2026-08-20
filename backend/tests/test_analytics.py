from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.api.analytics import AnalyzedTrade, _kst_date, analyze_trades, build_daily_pnl_points, build_metric


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


def test_analytics_calculates_average_cost_realized_profit_with_fees() -> None:
    analyzed, excluded = analyze_trades([
        trade(1, "buy", 100, 2),
        trade(2, "buy", 200, 1, 1),
        trade(3, "sell", 250, 2.5, 2),
    ])

    metric = build_metric(analyzed)

    assert excluded == 0
    assert metric.realized_pnl == 291.1875
    assert metric.total_fee == 0.5125
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


def test_analytics_uses_actual_paid_fee_when_available() -> None:
    bought = trade(1, "buy", 100, 1)
    sold = trade(2, "sell", 110, 1, 1)
    bought.paid_fee = 0.04
    sold.paid_fee = 0.06

    analyzed, excluded = analyze_trades([bought, sold])

    assert excluded == 0
    assert analyzed[-1].pnl == pytest.approx(9.9)
    assert build_metric(analyzed).total_fee == pytest.approx(0.1)


def test_deduct_reduces_average_cost_without_counting_as_trade() -> None:
    bought = trade(1, "buy", 88, 1)
    bought.position_key = 7
    deducted = trade(2, "sell", 88, 0.4, 1)
    deducted.event_type = "deduct"
    deducted.position_key = 7
    sold = trade(3, "sell", 90, 0.6, 2)
    sold.position_key = 7

    analyzed, excluded = analyze_trades([bought, deducted, sold])

    assert excluded == 0
    assert len(analyzed) == 2
    assert analyzed[-1].action == "sell"
    assert analyzed[-1].pnl == pytest.approx(1.1466)


def test_daily_pnl_accumulates_losses_from_zero_within_30_day_window() -> None:
    end = datetime(2026, 2, 1)
    analyzed = [
        AnalyzedTrade("KRW-BTC", "sell", 100, 500, 0.05, end - timedelta(days=30)),
        AnalyzedTrade("KRW-BTC", "sell", 100, -120, 0.05, end - timedelta(days=2)),
        AnalyzedTrade("KRW-BTC", "sell", 100, 20, 0.05, end),
    ]

    points = build_daily_pnl_points(analyzed, end.date())

    assert len(points) == 30
    assert points[0].cumulative_pnl == 0
    assert points[-3].cumulative_pnl == -120
    assert points[-1].cumulative_pnl == -100


def test_daily_pnl_groups_utc_trade_by_korean_calendar_date() -> None:
    # UTC 15시는 한국시간으로 다음 날 자정입니다.
    trade_time = datetime(2026, 1, 1, 15, 0)
    analyzed = [AnalyzedTrade("KRW-BTC", "sell", 100, 30, 0.05, trade_time)]

    points = build_daily_pnl_points(analyzed, datetime(2026, 1, 2).date())

    assert _kst_date(trade_time) == datetime(2026, 1, 2).date()
    assert points[-1].date == datetime(2026, 1, 2).date()
    assert points[-1].pnl == 30


def test_daily_and_cumulative_pnl_use_average_cost_fees_and_korean_dates() -> None:
    # 원가가 되는 매수는 30일 범위 밖이어도 평균원가 계산에는 포함되어야 합니다.
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
    assert points[-2].pnl == -10.045
    assert points[-2].cumulative_pnl == -10.045
    assert points[-1].date == datetime(2026, 1, 2).date()
    assert points[-1].pnl == 59.82
    assert points[-1].cumulative_pnl == 49.775

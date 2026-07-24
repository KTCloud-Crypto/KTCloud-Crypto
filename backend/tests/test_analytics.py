from datetime import datetime, timedelta
from types import SimpleNamespace

from app.api.analytics import AnalyzedTrade, analyze_trades, build_daily_pnl_points, build_metric


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

from datetime import datetime, timedelta
from types import SimpleNamespace

from app.api.analytics import analyze_trades, build_metric


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

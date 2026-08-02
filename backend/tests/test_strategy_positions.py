from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.strategy_positions import calculate_position


def _execution(identifier: int, action: str, volume: float, price: float):
    return SimpleNamespace(
        id=identifier,
        action=action,
        status="success",
        executed_volume=volume,
        average_price=price,
        price=price,
        created_at=datetime(2026, 1, 1) + timedelta(minutes=identifier),
    )


def test_position_keeps_weighted_average_after_partial_sell() -> None:
    position = calculate_position([
        _execution(1, "buy", 2, 100),
        _execution(2, "buy", 1, 130),
        _execution(3, "sell", 1, 150),
    ])

    assert position.volume == 2
    assert position.average_buy_price == 110


def test_position_is_flat_after_full_sell() -> None:
    position = calculate_position([
        _execution(1, "buy", 1, 100),
        _execution(2, "sell", 1, 120),
    ])

    assert position.volume == 0
    assert position.average_buy_price is None

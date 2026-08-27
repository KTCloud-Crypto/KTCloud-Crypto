from app.strategy.risk_exit import triggered_exit_source


def test_stop_loss_boundary_triggers_exit() -> None:
    assert triggered_exit_source(100, 95, 0.05, 0.1) == "stop_loss"


def test_take_profit_boundary_triggers_exit() -> None:
    assert triggered_exit_source(100, 110, 0.05, 0.1) == "take_profit"


def test_price_inside_exit_range_keeps_position() -> None:
    assert triggered_exit_source(100, 103, 0.05, 0.1) is None

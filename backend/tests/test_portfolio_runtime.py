from unittest.mock import patch

from app.portfolio.worker import monitor_positions_once


def test_monitor_positions_once_uses_existing_portfolio_monitor() -> None:
    with patch(
        "app.portfolio.worker.monitor_position_mismatches",
        return_value=(2, 1),
    ) as monitor:
        result = monitor_positions_once()

    monitor.assert_called_once_with()
    assert result == (2, 1)

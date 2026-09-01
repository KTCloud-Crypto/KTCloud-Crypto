from unittest.mock import patch

from fastapi.testclient import TestClient

from app.portfolio.main import app as portfolio_app
from app.portfolio.worker import monitor_positions_once


def test_monitor_positions_once_uses_existing_portfolio_monitor() -> None:
    with patch(
        "app.portfolio.worker.monitor_position_mismatches",
        return_value=(2, 1),
    ) as monitor:
        result = monitor_positions_once()

    monitor.assert_called_once_with()
    assert result == (2, 1)


def test_portfolio_api_entrypoint_exposes_health() -> None:
    response = TestClient(portfolio_app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

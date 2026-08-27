from unittest.mock import patch

from app.trading.worker import (
    reconcile_orders_once,
    recover_executions_once,
)


def test_reconcile_orders_once_uses_existing_reconciliation_service() -> None:
    with patch(
        "app.trading.worker.reconcile_pending_orders",
        return_value=2,
    ) as reconcile:
        settled = reconcile_orders_once()

    reconcile.assert_called_once_with()
    assert settled == 2


def test_recover_executions_once_uses_existing_recovery_service() -> None:
    with patch(
        "app.trading.worker.recover_stale_executions",
        return_value=(3, 1),
    ) as recover:
        result = recover_executions_once()

    recover.assert_called_once_with()
    assert result == (3, 1)

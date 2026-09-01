from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from app.messaging.envelope import MessageEnvelope
from app.messaging.sqs import QueueMessage
from app.portfolio.reconciliation_events import enqueue_position_reconciled
from app.trading.reconciliation_events import apply_position_reconciled
from app.trading.worker import process_message


def _envelope() -> MessageEnvelope:
    return MessageEnvelope.create(
        message_type="PositionReconciled",
        producer="portfolio",
        payload={"adjustment_id": 8, "user_strategy_id": 11},
    )


def test_portfolio_reconciliation_event_uses_adjustment_idempotency_key() -> None:
    db = MagicMock()
    adjustment = SimpleNamespace(id=8, user_strategy_id=11)

    message = enqueue_position_reconciled(db, adjustment)

    assert message.message_type == "PositionReconciled"
    assert message.idempotency_key == "position-adjustment:8"
    assert message.payload == {"adjustment_id": 8, "user_strategy_id": 11}


def test_trading_consumer_owns_uncertain_execution_update() -> None:
    execution = SimpleNamespace(status="uncertain", error_message=None)
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [execution]
    context = MagicMock()
    context.__enter__.return_value = db
    context.__exit__.return_value = None

    with patch("app.trading.reconciliation_events.SessionLocal", return_value=context):
        assert apply_position_reconciled(_envelope()) == 1

    assert execution.status == "reconciled"
    assert "실제 잔고 차이" in execution.error_message
    db.commit.assert_called_once()


def test_trading_worker_routes_position_reconciliation_before_ack() -> None:
    queue = Mock()
    message = QueueMessage("receipt", _envelope(), 1)

    with patch("app.trading.worker.apply_position_reconciled", return_value=1) as apply:
        process_message(queue, message)

    apply.assert_called_once_with(message.envelope)
    queue.acknowledge.assert_called_once_with(message)

from unittest.mock import MagicMock, patch

from app.messaging.envelope import MessageEnvelope
from app.messaging.strategy_commands import apply_allocation_changed


def test_allocation_changed_is_applied_by_strategy_consumer() -> None:
    subscription = MagicMock()
    db = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = db
    context.__exit__.return_value = None
    db.get.return_value = subscription
    envelope = MessageEnvelope.create(
        message_type="AllocationChanged",
        producer="trading",
        payload={"execution_id": 41, "user_strategy_id": 9, "allocated_amount": 12_345},
    )

    with patch("app.messaging.strategy_commands.SessionLocal", return_value=context):
        result = apply_allocation_changed(envelope)

    assert result.updated is True
    assert subscription.allocated_amount == 12_345.0
    db.commit.assert_called_once()

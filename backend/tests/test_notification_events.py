from unittest.mock import MagicMock, patch

from app.core.database import SessionLocal
from app.messaging.envelope import MessageEnvelope
from app.messaging.notification_events import enqueue_notification_requested
from app.messaging.sqs import QueueMessage
from app.models.message_outbox import MessageOutbox
from app.notification.delivery import deliver_notification
from app.workers.outbox_publisher_runtime import RoutedQueuePublisher
from app.notification.worker import process_notification


def test_notification_request_is_written_to_producer_outbox() -> None:
    with SessionLocal() as db:
        assert enqueue_notification_requested(
            db,
            chat_id="1234",
            message="hello",
            producer="trading-worker",
            notification_type="order_execution",
            user_id=7,
            idempotency_key="test-notification:7",
        )
        db.commit()

        row = db.query(MessageOutbox).filter_by(idempotency_key="test-notification:7").one()
        assert row.message_type == "NotificationRequested"
        assert row.payload == {
            "chat_id": "1234",
            "message": "hello",
            "notification_type": "order_execution",
            "user_id": 7,
        }


def test_notification_delivery_is_owned_by_notification_service() -> None:
    envelope = MessageEnvelope.create(
        message_type="NotificationRequested",
        producer="portfolio-worker",
        payload={
            "chat_id": "1234",
            "message": "position warning",
            "notification_type": "position_mismatch",
            "user_id": 7,
        },
    )
    with patch("app.notification.delivery.send_message", return_value=True) as send:
        assert deliver_notification(envelope) is True
    send.assert_called_once_with("1234", "position warning")


def test_outbox_routes_notification_request_to_notification_queue() -> None:
    trading, strategy, notification = MagicMock(), MagicMock(), MagicMock()
    with patch(
        "app.workers.outbox_publisher_runtime.SqsQueueAdapter.from_settings",
        side_effect=[trading, strategy, notification],
    ):
        publisher = RoutedQueuePublisher()
    envelope = MessageEnvelope.create(
        message_type="NotificationRequested",
        producer="identity-api",
        payload={"chat_id": "1234", "message": "hello"},
    )
    notification.publish.return_value = "transport-id"

    assert publisher.publish(envelope) == "transport-id"
    notification.publish.assert_called_once_with(envelope, delay_seconds=0)
    trading.publish.assert_not_called()
    strategy.publish.assert_not_called()


def test_notification_worker_acks_only_successful_delivery() -> None:
    queue = MagicMock()
    envelope = MessageEnvelope.create(
        message_type="NotificationRequested",
        producer="trading-worker",
        payload={"chat_id": "1234", "message": "hello"},
    )
    message = QueueMessage("receipt", envelope, 1)
    with patch("app.notification.worker.deliver_notification", return_value=True):
        assert process_notification(queue, message) is True
    queue.acknowledge.assert_called_once_with(message)

    queue.reset_mock()
    with patch("app.notification.worker.deliver_notification", return_value=False):
        assert process_notification(queue, message) is False
    queue.acknowledge.assert_not_called()

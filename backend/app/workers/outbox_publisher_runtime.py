from __future__ import annotations

import logging
import signal
import threading

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import configure_logging, log_event
from app.messaging.outbox import OutboxPublisher
from app.messaging.envelope import MessageEnvelope
from app.messaging.sqs import SqsQueueAdapter


configure_logging("outbox-publisher")
logger = logging.getLogger(__name__)


class RoutedQueuePublisher:
    """메시지 계약별로 이미 존재하는 SQS command queue를 선택합니다."""

    def __init__(self) -> None:
        self._trading = SqsQueueAdapter.from_settings(settings.sqs_trading_command_queue_name)
        self._strategy = SqsQueueAdapter.from_settings(settings.sqs_strategy_command_queue_name)
        self._notification = SqsQueueAdapter.from_settings(settings.sqs_notification_queue_name)

    def publish(self, envelope: MessageEnvelope, *, delay_seconds: int = 0) -> str:
        if envelope.message_type == "AllocationChanged":
            queue = self._strategy
        elif envelope.message_type == "NotificationRequested":
            queue = self._notification
        else:
            queue = self._trading
        return queue.publish(envelope, delay_seconds=delay_seconds)


def publish_once(publisher: OutboxPublisher) -> tuple[int, int, int]:
    with SessionLocal() as db:
        result = publisher.publish_pending(db)
        db.commit()
    return result.selected, result.published, result.failed


def main() -> None:
    stop_event = threading.Event()

    def request_stop(*_: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    publisher = OutboxPublisher(RoutedQueuePublisher())
    log_event(logger, logging.INFO, "outbox_publisher_started")
    while not stop_event.is_set():
        try:
            selected, published, failed = publish_once(publisher)
            if selected:
                log_event(
                    logger,
                    logging.INFO,
                    "outbox_publish_cycle",
                    selected=selected,
                    published=published,
                    failed=failed,
                )
        except Exception:
            logger.exception("Outbox publish cycle failed; retrying")
        stop_event.wait(max(0.1, settings.outbox_poll_seconds))
    log_event(logger, logging.INFO, "outbox_publisher_stopped")


if __name__ == "__main__":
    main()

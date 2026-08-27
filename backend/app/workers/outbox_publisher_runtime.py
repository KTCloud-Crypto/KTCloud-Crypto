from __future__ import annotations

import logging
import signal
import threading

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import configure_logging, log_event
from app.messaging.outbox import OutboxPublisher
from app.messaging.sqs import SqsQueueAdapter


configure_logging("outbox-publisher")
logger = logging.getLogger(__name__)


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

    publisher = OutboxPublisher(SqsQueueAdapter.from_settings())
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

from __future__ import annotations

import asyncio
import logging
import signal
import threading

from app.core.logging import configure_logging, log_event
from app.core.config import settings
from app.messaging.sqs import SqsQueueAdapter
from app.notification.delivery import deliver_notification
from app.notification.poller import run_telegram_poller


configure_logging("notification-worker")
logger = logging.getLogger(__name__)


def process_notification(queue: SqsQueueAdapter, message) -> bool:
    delivered = deliver_notification(message.envelope)
    if delivered:
        queue.acknowledge(message)
        log_event(
            logger,
            logging.INFO,
            "notification_delivered",
            message_id=str(message.envelope.message_id),
            notification_type=message.envelope.payload.get("notification_type"),
        )
    return delivered


def consume_notifications(stop_event) -> None:
    queue = SqsQueueAdapter.from_settings(settings.sqs_notification_queue_name)
    while not stop_event.is_set():
        try:
            for message in queue.receive(
                max_messages=10,
                wait_time_seconds=10,
                visibility_timeout=settings.sqs_notification_visibility_timeout_seconds,
            ):
                if not process_notification(queue, message):
                    logger.warning(
                        "Notification delivery failed; leaving message unacknowledged: message_id=%s",
                        message.envelope.message_id,
                    )
        except Exception:
            logger.exception("Notification receive failed; retrying")
            stop_event.wait(1)


async def main() -> None:
    stop_event = asyncio.Event()
    delivery_stop_event = threading.Event()
    loop = asyncio.get_running_loop()
    def request_stop() -> None:
        stop_event.set()
        delivery_stop_event.set()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signal_name, request_stop)

    log_event(logger, logging.INFO, "notification_worker_started")
    poller_task = asyncio.create_task(
        run_telegram_poller(stop_event),
        name="telegram-poller",
    )
    delivery_task = asyncio.create_task(
        asyncio.to_thread(consume_notifications, delivery_stop_event),
        name="notification-delivery",
    )
    await stop_event.wait()
    await asyncio.gather(poller_task, delivery_task, return_exceptions=True)
    log_event(logger, logging.INFO, "notification_worker_stopped")


if __name__ == "__main__":
    asyncio.run(main())

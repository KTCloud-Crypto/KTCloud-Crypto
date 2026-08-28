from __future__ import annotations

import asyncio
import logging
import signal

from app.core.logging import configure_logging, log_event
from app.notification.poller import run_telegram_poller


configure_logging("notification-worker")
logger = logging.getLogger(__name__)


async def main() -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signal_name, stop_event.set)

    log_event(logger, logging.INFO, "notification_worker_started")
    poller_task = asyncio.create_task(
        run_telegram_poller(stop_event),
        name="telegram-poller",
    )
    await stop_event.wait()
    await asyncio.gather(poller_task, return_exceptions=True)
    log_event(logger, logging.INFO, "notification_worker_stopped")


if __name__ == "__main__":
    asyncio.run(main())

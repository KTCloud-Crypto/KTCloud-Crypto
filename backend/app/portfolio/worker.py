from __future__ import annotations

import logging
import signal
import threading

from prometheus_client import start_http_server

from app.core.config import settings
from app.core.logging import configure_logging, log_event
from app.core.metrics import WORKER_ERRORS
from app.portfolio.position_monitor import monitor_position_mismatches
from app.workers.task_observability import observe_worker_task


configure_logging("portfolio-worker")
logger = logging.getLogger(__name__)


def monitor_positions_once() -> tuple[int, int]:
    """실제 잔고와 전략 기록의 불일치를 한 번 검사합니다."""
    with observe_worker_task("position_monitor"):
        return monitor_position_mismatches()


def main() -> None:
    stop_event = threading.Event()

    def request_stop(*_: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    if settings.metrics_enabled:
        start_http_server(settings.portfolio_metrics_port)

    interval_seconds = max(10, settings.position_reconciliation_seconds)
    log_event(
        logger,
        logging.INFO,
        "portfolio_worker_started",
        interval_seconds=interval_seconds,
    )
    while not stop_event.is_set():
        try:
            checked, notifications = monitor_positions_once()
            log_event(
                logger,
                logging.INFO,
                "portfolio_reconciliation_cycle",
                checked_users=checked,
                notifications=notifications,
            )
        except Exception:
            WORKER_ERRORS.labels("position_monitor").inc()
            logger.exception("Position mismatch monitoring failed; retrying on next cycle")
        stop_event.wait(interval_seconds)
    log_event(logger, logging.INFO, "portfolio_worker_stopped")


if __name__ == "__main__":
    main()

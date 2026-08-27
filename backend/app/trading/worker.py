from __future__ import annotations

import asyncio
import logging
import signal
import threading
from collections.abc import Callable

from prometheus_client import start_http_server

from app.core.config import settings
from app.core.metrics import WORKER_ERRORS, WORKER_RECOVERIES
from app.core.logging import configure_logging, log_event
from app.messaging.sqs import QueueMessage, SqsQueueAdapter
from app.messaging.trading_commands import execute_strategy_signal
from app.trading.execution_recovery import recover_stale_executions
from app.trading.order_reconciliation import reconcile_pending_orders
from app.workers.task_observability import observe_worker_task


configure_logging("trading")
logger = logging.getLogger(__name__)


def process_message(queue: SqsQueueAdapter, message: QueueMessage) -> None:
    result = asyncio.run(execute_strategy_signal(message.envelope))
    # 주문 실행 함수가 오류 없이 끝난 뒤에만 ACK합니다. 실패한 메시지는
    # visibility timeout 이후 재전달되고, 반복 실패 시 DLQ로 이동합니다.
    queue.acknowledge(message)
    log_event(
        logger,
        logging.INFO,
        "trading_signal_processed",
        message_id=str(message.envelope.message_id),
        correlation_id=message.envelope.correlation_id,
        receive_count=message.receive_count,
        signal_id=result.signal_id,
        target_user_id=result.target_user_id,
        target_mode=result.target_mode,
        execution_count=result.execution_count,
    )


def reconcile_orders_once() -> int:
    """접수·부분 체결 주문을 한 번 확인합니다."""
    with observe_worker_task("order_reconciliation"):
        settled = reconcile_pending_orders()
    if settled:
        logger.info("Pending orders settled: count=%s", settled)
    return settled


def recover_executions_once() -> tuple[int, int]:
    """중단 중 남은 준비 상태 실행을 한 번 안전하게 정리합니다."""
    with observe_worker_task("execution_recovery"):
        recovered, uncertain = recover_stale_executions()
    if recovered:
        WORKER_RECOVERIES.labels("uncertain" if uncertain else "recovered").inc(recovered)
        logger.warning(
            "Stale executions recovered: count=%s uncertain=%s",
            recovered,
            uncertain,
        )
    return recovered, uncertain


def run_periodic_task(
    stop_event: threading.Event,
    *,
    task_name: str,
    interval_seconds: float,
    task: Callable[[], object],
) -> None:
    """Trading 소유의 주기 작업을 consumer 수명과 함께 실행합니다."""
    while not stop_event.is_set():
        try:
            task()
        except Exception:
            WORKER_ERRORS.labels(task_name).inc()
            logger.exception("Trading periodic task failed: task=%s", task_name)
        stop_event.wait(interval_seconds)


def main() -> None:
    stop_event = threading.Event()

    def request_stop(*_: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    if settings.metrics_enabled:
        start_http_server(settings.trading_metrics_port)

    queue = SqsQueueAdapter.from_settings()
    periodic_threads = [
        threading.Thread(
            target=run_periodic_task,
            kwargs={
                "stop_event": stop_event,
                "task_name": "order_reconciliation",
                "interval_seconds": 5,
                "task": reconcile_orders_once,
            },
            name="order-reconciliation",
            daemon=True,
        ),
        threading.Thread(
            target=run_periodic_task,
            kwargs={
                "stop_event": stop_event,
                "task_name": "execution_recovery",
                "interval_seconds": 30,
                "task": recover_executions_once,
            },
            name="execution-recovery",
            daemon=True,
        ),
    ]
    for thread in periodic_threads:
        thread.start()
    log_event(logger, logging.INFO, "trading_started")
    while not stop_event.is_set():
        try:
            messages = queue.receive(max_messages=10, wait_time_seconds=10)
            for message in messages:
                try:
                    process_message(queue, message)
                except Exception:
                    logger.exception(
                        "Trading message failed; leaving it unacknowledged",
                        extra={
                            "message_id": str(message.envelope.message_id),
                            "message_type": message.envelope.message_type,
                            "receive_count": message.receive_count,
                        },
                    )
        except Exception:
            logger.exception("Trading receive failed; retrying")
            stop_event.wait(1)
    for thread in periodic_threads:
        thread.join(timeout=1)
    log_event(logger, logging.INFO, "trading_stopped")


if __name__ == "__main__":
    main()

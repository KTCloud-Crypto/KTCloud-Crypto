from __future__ import annotations

import asyncio
import logging
import signal
import time
from contextlib import contextmanager
from collections.abc import Iterator
from prometheus_client import start_http_server

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.metrics import (
    WORKER_ERRORS,
    WORKER_RECOVERIES,
    WORKER_TASK_DURATION,
    WORKER_TASK_IN_PROGRESS,
    WORKER_TASK_LAST_SUCCESS,
    WORKER_TASK_RUNS,
)
from app.core.database import SessionLocal
from app.models import ApiKey, Strategy, StrategyRuntime, StrategySignal, Trade, User, UserStrategy
from app.services.market_stream import TradeTick, UpbitTradeStream
from app.services.telegram_poller import run_telegram_poller
from app.services.strategy_engine import StrategyEngine
from app.services.strategy_catalog import seed_strategy_catalog
from app.services.order_reconciliation import reconcile_pending_orders
from app.services.position_monitor import monitor_position_mismatches
from app.services.execution_recovery import recover_stale_executions

configure_logging("strategy-worker")
logger = logging.getLogger(__name__)


@contextmanager
def observe_worker_task(task: str) -> Iterator[None]:
    """Worker 반복 작업의 실행 상태와 결과를 Prometheus에 기록합니다."""
    started_at = time.monotonic()
    WORKER_TASK_IN_PROGRESS.labels(task).inc()
    try:
        yield
    except Exception:
        WORKER_TASK_RUNS.labels(task, "error").inc()
        raise
    else:
        WORKER_TASK_RUNS.labels(task, "success").inc()
        WORKER_TASK_LAST_SUCCESS.labels(task).set_to_current_time()
    finally:
        WORKER_TASK_DURATION.labels(task).observe(time.monotonic() - started_at)
        WORKER_TASK_IN_PROGRESS.labels(task).dec()


def initialize_database() -> None:
    with SessionLocal() as db:
        seed_strategy_catalog(db)


class MarketStreamMonitor:
    """WebSocket 체결 수신량과 종목별 최신 가격을 주기적으로 기록합니다."""

    def __init__(self):
        self.count = 0
        self.latest: dict[str, TradeTick] = {}

    async def on_trade(self, tick: TradeTick) -> None:
        self.count += 1
        self.latest[tick.market] = tick

    async def report(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=60)
            except asyncio.TimeoutError:
                prices = {market: tick.price for market, tick in self.latest.items()}
                logger.info("Market stream healthy: ticks=%s latest=%s", self.count, prices)


async def reconcile_orders_loop(stop_event: asyncio.Event) -> None:
    """접수·부분 체결 상태의 실전 주문을 종료 시점까지 계속 확인합니다."""
    while not stop_event.is_set():
        try:
            with observe_worker_task("order_reconciliation"):
                settled = await asyncio.to_thread(reconcile_pending_orders)
            if settled:
                logger.info("Pending orders settled: count=%s", settled)
        except Exception:
            WORKER_ERRORS.labels("order_reconciliation").inc()
            logger.exception("Pending order reconciliation failed; retrying on next cycle")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=5)
        except asyncio.TimeoutError:
            pass


async def monitor_positions_loop(stop_event: asyncio.Event) -> None:
    """실제 잔고와 전략 기록 차이를 감지하고 새로운 사건만 알립니다."""
    while not stop_event.is_set():
        try:
            with observe_worker_task("position_monitor"):
                checked, notifications = await asyncio.to_thread(monitor_position_mismatches)
            if notifications:
                logger.info(
                    "Position mismatch notifications sent: users=%s notifications=%s",
                    checked,
                    notifications,
                )
        except Exception:
            WORKER_ERRORS.labels("position_monitor").inc()
            logger.exception("Position mismatch monitoring failed; retrying on next cycle")
        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=max(10, settings.position_reconciliation_seconds),
            )
        except asyncio.TimeoutError:
            pass


async def recover_executions_loop(stop_event: asyncio.Event) -> None:
    """중단된 주문 준비 레코드를 주기적으로 안전 상태로 전환합니다."""
    while not stop_event.is_set():
        try:
            with observe_worker_task("execution_recovery"):
                recovered, uncertain = await asyncio.to_thread(recover_stale_executions)
            if recovered:
                WORKER_RECOVERIES.labels("uncertain" if uncertain else "recovered").inc(recovered)
                logger.warning(
                    "Stale executions recovered: count=%s uncertain=%s",
                    recovered,
                    uncertain,
                )
        except Exception:
            WORKER_ERRORS.labels("execution_recovery").inc()
            logger.exception("Stale execution recovery failed; retrying on next cycle")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=30)
        except asyncio.TimeoutError:
            pass


async def main() -> None:
    stop_event = asyncio.Event()
    if settings.metrics_enabled:
        start_http_server(settings.worker_metrics_port)
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signal_name, stop_event.set)

    await asyncio.to_thread(initialize_database)

    monitor = MarketStreamMonitor()
    engine = StrategyEngine()
    await engine.refresh()

    async def on_trade(tick: TradeTick) -> None:
        await monitor.on_trade(tick)
        await engine.on_trade(tick)

    stream = UpbitTradeStream(
        url=settings.upbit_ws_url,
        markets=settings.watch_market_list,
        on_trade=on_trade,
    )

    tasks = [
        asyncio.create_task(stream.run(stop_event), name="upbit-trade-stream"),
        asyncio.create_task(monitor.report(stop_event), name="market-stream-monitor"),
        asyncio.create_task(run_telegram_poller(stop_event), name="telegram-poller"),
        asyncio.create_task(engine.refresh_loop(stop_event), name="strategy-refresh"),
        asyncio.create_task(reconcile_orders_loop(stop_event), name="order-reconciliation"),
        asyncio.create_task(monitor_positions_loop(stop_event), name="position-mismatch-monitor"),
        asyncio.create_task(recover_executions_loop(stop_event), name="execution-recovery"),
    ]

    logger.info("Strategy worker started")
    await stop_event.wait()
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Strategy worker stopped")


if __name__ == "__main__":
    asyncio.run(main())

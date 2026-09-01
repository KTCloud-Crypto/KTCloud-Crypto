from __future__ import annotations

import asyncio
import logging
import signal
import threading

from prometheus_client import start_http_server

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import configure_logging
from app.market_data import TradeTick, UpbitTradeStream
from app.messaging.sqs import QueueMessage, SqsQueueAdapter
from app.messaging.strategy_commands import apply_allocation_changed
import app.models  # noqa: F401  # SQLAlchemy metadata에 모든 ORM 모델을 등록합니다.
from app.strategy.strategy_catalog import seed_strategy_catalog
from app.strategy.strategy_engine import StrategyEngine


configure_logging("strategy-worker")
logger = logging.getLogger(__name__)


def initialize_database() -> None:
    with SessionLocal() as db:
        seed_strategy_catalog(db)


async def initialize_until_ready(stop_event: asyncio.Event) -> StrategyEngine | None:
    """DB가 늦게 준비되어도 Pod 재시작 루프 없이 초기화를 재시도합니다."""
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(initialize_database)
            engine = StrategyEngine()
            await engine.refresh()
            return engine
        except Exception:
            logger.exception("Strategy dependencies unavailable; retrying startup")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=2)
            except asyncio.TimeoutError:
                pass
    return None


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


def run_strategy_command_consumer(stop_event: threading.Event) -> None:
    """Trading 체결 이벤트를 받아 Strategy 소유 구독 상태만 갱신합니다."""
    queue = SqsQueueAdapter.from_settings(settings.sqs_strategy_command_queue_name)
    while not stop_event.is_set():
        try:
            for message in queue.receive(
                max_messages=10,
                wait_time_seconds=5,
                visibility_timeout=settings.sqs_strategy_visibility_timeout_seconds,
            ):
                _process_strategy_command(queue, message)
        except Exception:
            logger.exception("Strategy command receive failed; retrying")
            stop_event.wait(1)


def _process_strategy_command(queue: SqsQueueAdapter, message: QueueMessage) -> None:
    result = apply_allocation_changed(message.envelope)
    queue.acknowledge(message)
    logger.info(
        "Strategy allocation updated: execution_id=%s user_strategy_id=%s updated=%s",
        result.execution_id,
        result.user_strategy_id,
        result.updated,
    )


async def main() -> None:
    stop_event = asyncio.Event()
    command_stop_event = threading.Event()
    if settings.metrics_enabled:
        start_http_server(settings.worker_metrics_port)
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signal_name, stop_event.set)

    monitor = MarketStreamMonitor()
    engine = await initialize_until_ready(stop_event)
    if engine is None:
        logger.info("Strategy worker stopped before initialization completed")
        return

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
        asyncio.create_task(engine.refresh_loop(stop_event), name="strategy-refresh"),
    ]
    command_thread = threading.Thread(
        target=run_strategy_command_consumer,
        args=(command_stop_event,),
        name="strategy-command-consumer",
        daemon=True,
    )
    command_thread.start()

    logger.info("Strategy worker started")
    await stop_event.wait()
    command_stop_event.set()
    await asyncio.gather(*tasks, return_exceptions=True)
    command_thread.join(timeout=6)
    logger.info("Strategy worker stopped")


if __name__ == "__main__":
    asyncio.run(main())

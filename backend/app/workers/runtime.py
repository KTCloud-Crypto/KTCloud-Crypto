from __future__ import annotations

import asyncio
import logging
import signal
from prometheus_client import start_http_server

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.database import SessionLocal
import app.models  # noqa: F401  # SQLAlchemy metadata에 모든 ORM 모델을 등록합니다.
from app.market_data import TradeTick, UpbitTradeStream
from app.strategy.strategy_engine import StrategyEngine
from app.strategy.strategy_catalog import seed_strategy_catalog

configure_logging("strategy-worker")
logger = logging.getLogger(__name__)


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
        asyncio.create_task(engine.refresh_loop(stop_event), name="strategy-refresh"),
    ]

    logger.info("Strategy worker started")
    await stop_event.wait()
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Strategy worker stopped")


if __name__ == "__main__":
    asyncio.run(main())

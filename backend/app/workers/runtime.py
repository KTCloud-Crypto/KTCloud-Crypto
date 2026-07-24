from __future__ import annotations

import asyncio
import logging
import signal

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import ApiKey, Strategy, StrategyRuntime, StrategySignal, Trade, User, UserStrategy
from app.services.market_stream import TradeTick, UpbitTradeStream
from app.services.telegram_poller import run_telegram_poller
from app.services.strategy_engine import StrategyEngine
from app.services.strategy_catalog import seed_strategy_catalog
from app.services.order_reconciliation import reconcile_pending_orders
from app.services.position_monitor import monitor_position_mismatches
from app.services.execution_recovery import recover_stale_executions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
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


async def reconcile_orders_loop(stop_event: asyncio.Event) -> None:
    """접수·부분 체결 상태의 실전 주문을 종료 시점까지 계속 확인합니다."""
    while not stop_event.is_set():
        try:
            settled = await asyncio.to_thread(reconcile_pending_orders)
            if settled:
                logger.info("Pending orders settled: count=%s", settled)
        except Exception:
            logger.exception("Pending order reconciliation failed; retrying on next cycle")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=5)
        except asyncio.TimeoutError:
            pass


async def monitor_positions_loop(stop_event: asyncio.Event) -> None:
    """실제 잔고와 전략 기록 차이를 감지하고 새로운 사건만 알립니다."""
    while not stop_event.is_set():
        try:
            checked, notifications = await asyncio.to_thread(monitor_position_mismatches)
            if notifications:
                logger.info(
                    "Position mismatch notifications sent: users=%s notifications=%s",
                    checked,
                    notifications,
                )
        except Exception:
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
            recovered, uncertain = await asyncio.to_thread(recover_stale_executions)
            if recovered:
                logger.warning(
                    "Stale executions recovered: count=%s uncertain=%s",
                    recovered,
                    uncertain,
                )
        except Exception:
            logger.exception("Stale execution recovery failed; retrying on next cycle")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=30)
        except asyncio.TimeoutError:
            pass


async def main() -> None:
    stop_event = asyncio.Event()
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

    logger.info(
        "Strategy worker started: live_trading=%s",
        "enabled" if settings.live_trading_enabled else "disabled",
    )
    await stop_event.wait()
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Strategy worker stopped")


if __name__ == "__main__":
    asyncio.run(main())

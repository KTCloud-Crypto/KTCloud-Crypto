from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import websockets
from app.core.metrics import MARKET_LAST_TICK, WEBSOCKET_CONNECTIONS, WEBSOCKET_RECONNECTS

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TradeTick:
    market: str
    price: float
    volume: float
    timestamp_ms: int
    sequential_id: int | None


TradeCallback = Callable[[TradeTick], Awaitable[None]]


class UpbitTradeStream:
    """Upbit 공개 WebSocket 체결 스트림을 유지하고 정규화한 tick을 전달합니다."""

    def __init__(self, url: str, markets: list[str], on_trade: TradeCallback):
        if not markets:
            raise ValueError("감시할 Upbit 마켓이 한 개 이상 필요합니다.")
        self._url = url
        self._markets = markets
        self._on_trade = on_trade

    def _subscription(self) -> str:
        return json.dumps(
            [
                {"ticket": f"signaltrade-{int(time.time())}"},
                {"type": "trade", "codes": self._markets, "is_only_realtime": True},
                {"format": "DEFAULT"},
            ]
        )

    async def run(self, stop_event: asyncio.Event) -> None:
        backoff_seconds = 1.0

        while not stop_event.is_set():
            try:
                async with websockets.connect(
                    self._url,
                    ping_interval=30,
                    ping_timeout=20,
                    close_timeout=5,
                    max_queue=1024,
                ) as websocket:
                    WEBSOCKET_CONNECTIONS.labels("upbit").set(1)
                    await websocket.send(self._subscription())
                    backoff_seconds = 1.0
                    logger.info("Upbit WebSocket connected: markets=%s", self._markets)

                    while not stop_event.is_set():
                        raw = await asyncio.wait_for(websocket.recv(), timeout=90)
                        data = json.loads(raw)
                        if data.get("type") != "trade":
                            continue

                        tick = TradeTick(
                            market=data["code"],
                            price=float(data["trade_price"]),
                            volume=float(data["trade_volume"]),
                            timestamp_ms=int(data["trade_timestamp"]),
                            sequential_id=data.get("sequential_id"),
                        )
                        MARKET_LAST_TICK.labels(tick.market).set(time.time())
                        await self._on_trade(tick)

            except asyncio.CancelledError:
                WEBSOCKET_CONNECTIONS.labels("upbit").set(0)
                raise
            except Exception as error:
                WEBSOCKET_CONNECTIONS.labels("upbit").set(0)
                WEBSOCKET_RECONNECTS.labels("upbit").inc()
                logger.warning(
                    "Upbit WebSocket disconnected: retry_in=%ss error=%s",
                    backoff_seconds,
                    error,
                )
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=backoff_seconds)
                except asyncio.TimeoutError:
                    pass
                backoff_seconds = min(backoff_seconds * 2, 30.0)
        WEBSOCKET_CONNECTIONS.labels("upbit").set(0)

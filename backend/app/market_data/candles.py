from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.market_data.stream import TradeTick


@dataclass(frozen=True, slots=True)
class Candle:
    market: str
    interval_minutes: int
    open_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


CandleCallback = Callable[[Candle], Awaitable[None]]


class CandleBuilder:
    """체결 tick을 지정된 분 단위 OHLCV 캔들로 집계합니다."""

    def __init__(self, interval_minutes: int, on_close: CandleCallback):
        if interval_minutes <= 0:
            raise ValueError("캔들 주기는 1분 이상이어야 합니다.")
        self.interval_minutes = interval_minutes
        self._interval_ms = interval_minutes * 60 * 1000
        self._on_close = on_close
        self._current: dict[str, Candle] = {}

    def _bucket(self, timestamp_ms: int) -> int:
        return timestamp_ms - (timestamp_ms % self._interval_ms)

    async def on_trade(self, tick: TradeTick) -> None:
        bucket = self._bucket(tick.timestamp_ms)
        current = self._current.get(tick.market)

        if current is None:
            self._current[tick.market] = Candle(
                market=tick.market,
                interval_minutes=self.interval_minutes,
                open_time_ms=bucket,
                open=tick.price,
                high=tick.price,
                low=tick.price,
                close=tick.price,
                volume=tick.volume,
            )
            return

        if bucket < current.open_time_ms:
            return

        if bucket > current.open_time_ms:
            await self._on_close(current)
            self._current[tick.market] = Candle(
                market=tick.market,
                interval_minutes=self.interval_minutes,
                open_time_ms=bucket,
                open=tick.price,
                high=tick.price,
                low=tick.price,
                close=tick.price,
                volume=tick.volume,
            )
            return


        self._current[tick.market] = Candle(
            market=current.market,
            interval_minutes=current.interval_minutes,
            open_time_ms=current.open_time_ms,
            open=current.open,
            high=max(current.high, tick.price),
            low=min(current.low, tick.price),
            close=tick.price,
            volume=current.volume + tick.volume,
        )

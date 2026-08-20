import asyncio

from app.services.candles import Candle, CandleBuilder
from app.services.market_stream import TradeTick
from app.services.strategy_evaluators import (
    BollingerReentryEvaluator,
    BollingerSqueezeBreakoutEvaluator,
    DonchianBreakoutEvaluator,
    MacdCrossEvaluator,
    RsiReversalEvaluator,
    SmaCrossEvaluator,
)


def _tick(price: float, volume: float, timestamp_ms: int) -> TradeTick:
    return TradeTick("KRW-BTC", price, volume, timestamp_ms, None)


def _candle(close: float, index: int = 0, high: float | None = None, low: float | None = None) -> Candle:
    return Candle(
        market="KRW-BTC",
        interval_minutes=1,
        open_time_ms=index * 60_000,
        open=close,
        high=high if high is not None else close,
        low=low if low is not None else close,
        close=close,
        volume=1,
    )


def _candles(closes: list[float]) -> list[Candle]:
    return [_candle(close, index) for index, close in enumerate(closes)]


def test_candle_builder_closes_ohlcv_when_next_interval_starts() -> None:
    closed = []

    async def on_close(candle):
        closed.append(candle)

    async def scenario() -> None:
        builder = CandleBuilder(interval_minutes=15, on_close=on_close)
        await builder.on_trade(_tick(100, 1.0, 1_000))
        await builder.on_trade(_tick(110, 2.0, 2_000))
        await builder.on_trade(_tick(90, 3.0, 3_000))
        await builder.on_trade(_tick(105, 4.0, 4_000))
        await builder.on_trade(_tick(120, 1.0, 900_001))

    asyncio.run(scenario())
    assert len(closed) == 1
    candle = closed[0]
    assert (candle.open, candle.high, candle.low, candle.close, candle.volume) == (100, 110, 90, 105, 10)


def test_sma_cross_evaluator_detects_both_directions() -> None:
    buy = SmaCrossEvaluator(short_window=2, long_window=3)
    buy.warmup(_candles([3, 2, 1]))
    buy_result = buy.update(_candle(5, 4))
    assert buy_result and buy_result.action == "buy"
    assert buy_result.metrics["short_sma"] > buy_result.metrics["long_sma"]

    sell = SmaCrossEvaluator(short_window=2, long_window=3)
    sell.warmup(_candles([1, 2, 3]))
    sell_result = sell.update(_candle(0, 4))
    assert sell_result and sell_result.action == "sell"


def test_rsi_reversal_detects_threshold_reentry() -> None:
    buy = RsiReversalEvaluator(period=3, oversold=30, overbought=70)
    buy.warmup(_candles([100, 90, 80, 70]))
    assert buy.update(_candle(80, 5)).action == "buy"

    sell = RsiReversalEvaluator(period=3, oversold=30, overbought=70)
    sell.warmup(_candles([100, 110, 120, 130]))
    assert sell.update(_candle(120, 5)).action == "sell"


def test_macd_cross_detects_direction_change() -> None:
    buy = MacdCrossEvaluator(fast=2, slow=3, signal=2)
    buy.warmup(_candles([5, 4, 3, 2, 1]))
    assert buy.update(_candle(10, 6)).action == "buy"

    sell = MacdCrossEvaluator(fast=2, slow=3, signal=2)
    sell.warmup(_candles([1, 2, 3, 4, 5]))
    assert sell.update(_candle(0, 6)).action == "sell"


def test_bollinger_reentry_detects_return_inside_band() -> None:
    evaluator = BollingerReentryEvaluator(window=3, deviation=1)
    evaluator.warmup(_candles([10, 10, 10, 0]))
    result = evaluator.update(_candle(10, 5))
    assert result and result.action == "buy"
    assert result.metrics["lower"] < result.metrics["middle"] < result.metrics["upper"]


def test_bollinger_squeeze_uses_the_shared_band_calculation() -> None:
    evaluator = BollingerSqueezeBreakoutEvaluator(
        window=3,
        deviation=1,
        squeeze_lookback=2,
        squeeze_ratio=0.9,
        squeeze_valid_candles=2,
    )
    evaluator.warmup(_candles([10, 11, 10, 11, 10, 11]))

    result = evaluator.update(_candle(10, 7))

    assert result is not None
    assert result.metrics["lower"] < result.metrics["middle"] < result.metrics["upper"]


def test_donchian_breakout_uses_previous_candles_only() -> None:
    evaluator = DonchianBreakoutEvaluator(window=3)
    evaluator.warmup([
        _candle(7, 1, high=10, low=5),
        _candle(8, 2, high=9, low=6),
        _candle(9, 3, high=10, low=7),
    ])
    result = evaluator.update(_candle(11, 4, high=12, low=8))
    assert result and result.action == "buy"
    assert result.metrics == {"upper": 10, "lower": 5}

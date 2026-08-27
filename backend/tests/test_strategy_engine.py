import asyncio
from unittest.mock import AsyncMock, patch

from app.market_data import Candle
from app.strategy.strategy_engine import StrategyDefinition, StrategyEngine
from app.strategy.strategy_evaluators import StrategyEvaluation


def _candle(open_time_ms: int, close: float, volume: float) -> Candle:
    return Candle(
        market="KRW-BTC",
        interval_minutes=60,
        open_time_ms=open_time_ms,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=volume,
    )


class RecordingEvaluator:
    def __init__(self) -> None:
        self.received: list[Candle] = []

    def update(self, candle: Candle) -> StrategyEvaluation:
        self.received.append(candle)
        return StrategyEvaluation(None, {"close": candle.close})


def test_candle_close_uses_official_completed_candle_instead_of_partial_builder_candle() -> None:
    engine = StrategyEngine()
    key = ("test_v1", "KRW-BTC", 60)
    definition = StrategyDefinition(1, "test_v1", "KRW-BTC", 60, {})
    evaluator = RecordingEvaluator()
    engine._definitions[key] = definition
    engine._evaluators[key] = evaluator
    engine._last_processed_candle[key] = 0
    partial = _candle(3_600_000, close=101, volume=2)
    official = _candle(3_600_000, close=109, volume=50)

    with (
        patch(
            "app.strategy.strategy_engine.fetch_completed_minute_candles",
            return_value=[official],
        ),
        patch("app.strategy.strategy_engine._save_evaluation", return_value=None),
    ):
        asyncio.run(engine.on_candle_close(partial))

    assert evaluator.received == [official]
    assert evaluator.received[0].close == 109
    assert evaluator.received[0].volume == 50


def test_candle_already_included_in_warmup_is_not_processed_again() -> None:
    engine = StrategyEngine()
    key = ("test_v1", "KRW-BTC", 60)
    definition = StrategyDefinition(1, "test_v1", "KRW-BTC", 60, {})
    evaluator = RecordingEvaluator()
    completed = _candle(3_600_000, close=109, volume=50)
    engine._definitions[key] = definition
    engine._evaluators[key] = evaluator
    engine._last_processed_candle[key] = completed.open_time_ms

    with patch(
        "app.strategy.strategy_engine.fetch_completed_minute_candles",
        return_value=[completed],
    ):
        asyncio.run(engine.on_candle_close(completed))

    assert evaluator.received == []


def test_transient_rest_failure_is_retried_without_escaping_to_websocket() -> None:
    engine = StrategyEngine()
    key = ("test_v1", "KRW-BTC", 60)
    definition = StrategyDefinition(1, "test_v1", "KRW-BTC", 60, {})
    evaluator = RecordingEvaluator()
    completed = _candle(3_600_000, close=109, volume=50)
    engine._definitions[key] = definition
    engine._evaluators[key] = evaluator
    engine._last_processed_candle[key] = 0

    with (
        patch(
            "app.strategy.strategy_engine.fetch_completed_minute_candles",
            side_effect=[RuntimeError("temporary failure"), [completed]],
        ),
        patch("app.strategy.strategy_engine.asyncio.sleep", new=AsyncMock()),
        patch("app.strategy.strategy_engine._save_evaluation", return_value=None),
    ):
        asyncio.run(engine.on_candle_close(completed))

    assert evaluator.received == [completed]


def test_recent_unprocessed_candle_is_recovered_in_order() -> None:
    engine = StrategyEngine()
    key = ("test_v1", "KRW-BTC", 60)
    definition = StrategyDefinition(1, "test_v1", "KRW-BTC", 60, {})
    evaluator = RecordingEvaluator()
    missed = _candle(3_600_000, close=105, volume=40)
    current = _candle(7_200_000, close=109, volume=50)
    engine._definitions[key] = definition
    engine._evaluators[key] = evaluator
    engine._last_processed_candle[key] = 0

    with (
        patch(
            "app.strategy.strategy_engine.fetch_completed_minute_candles",
            return_value=[current, missed],
        ),
        patch("app.strategy.strategy_engine._save_evaluation", return_value=None),
    ):
        asyncio.run(engine.on_candle_close(current))

    assert evaluator.received == [missed, current]

"""전략별 지표 계산기를 동일한 입력·출력 규격으로 제공합니다."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import sqrt
from typing import Protocol

from app.services.candles import Candle


@dataclass(frozen=True, slots=True)
class StrategyEvaluation:
    action: str | None
    metrics: dict[str, float]


class StrategyEvaluator(Protocol):
    required_history: int

    def warmup(self, candles: list[Candle]) -> None: ...

    def update(self, candle: Candle) -> StrategyEvaluation | None: ...


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


class SmaCrossEvaluator:
    """단기·장기 단순이동평균의 교차를 판정합니다."""

    def __init__(self, short_window: int, long_window: int):
        if short_window <= 0 or long_window <= short_window:
            raise ValueError("SMA 기간은 0 < short < long 조건이어야 합니다.")
        self.short_window = short_window
        self.long_window = long_window
        self.required_history = long_window + 1
        self._closes: deque[float] = deque(maxlen=self.required_history)

    def warmup(self, candles: list[Candle]) -> None:
        self._closes.clear()
        self._closes.extend(candle.close for candle in candles[-self.required_history :])

    def update(self, candle: Candle) -> StrategyEvaluation | None:
        self._closes.append(candle.close)
        if len(self._closes) < self.required_history:
            return None

        values = list(self._closes)
        previous_short = _mean(values[-self.short_window - 1 : -1])
        previous_long = _mean(values[-self.long_window - 1 : -1])
        current_short = _mean(values[-self.short_window :])
        current_long = _mean(values[-self.long_window :])
        action = None
        if previous_short <= previous_long and current_short > current_long:
            action = "buy"
        elif previous_short >= previous_long and current_short < current_long:
            action = "sell"
        return StrategyEvaluation(action, {"short_sma": current_short, "long_sma": current_long})


class RsiReversalEvaluator:
    """Wilder RSI가 과매도·과매수 구간에서 복귀하는 시점을 판정합니다."""

    def __init__(self, period: int, oversold: float, overbought: float):
        if period <= 1 or not 0 < oversold < overbought < 100:
            raise ValueError("RSI 설정값이 올바르지 않습니다.")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.required_history = period + 100
        self._last_close: float | None = None
        self._avg_gain: float | None = None
        self._avg_loss: float | None = None
        self._previous_rsi: float | None = None

    @staticmethod
    def _rsi(avg_gain: float, avg_loss: float) -> float:
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
        return 100 - (100 / (1 + avg_gain / avg_loss))

    def warmup(self, candles: list[Candle]) -> None:
        closes = [candle.close for candle in candles]
        self._last_close = None
        self._avg_gain = None
        self._avg_loss = None
        self._previous_rsi = None
        if len(closes) < self.period + 1:
            if closes:
                self._last_close = closes[-1]
            return

        changes = [current - previous for previous, current in zip(closes, closes[1:])]
        initial = changes[: self.period]
        self._avg_gain = sum(max(change, 0) for change in initial) / self.period
        self._avg_loss = sum(max(-change, 0) for change in initial) / self.period
        self._previous_rsi = self._rsi(self._avg_gain, self._avg_loss)
        for change in changes[self.period :]:
            self._previous_rsi = self._advance(change)
        self._last_close = closes[-1]

    def _advance(self, change: float) -> float:
        assert self._avg_gain is not None and self._avg_loss is not None
        self._avg_gain = (self._avg_gain * (self.period - 1) + max(change, 0)) / self.period
        self._avg_loss = (self._avg_loss * (self.period - 1) + max(-change, 0)) / self.period
        rsi = self._rsi(self._avg_gain, self._avg_loss)
        return rsi

    def update(self, candle: Candle) -> StrategyEvaluation | None:
        if self._last_close is None or self._avg_gain is None or self._avg_loss is None:
            self._last_close = candle.close
            return None
        current_rsi = self._advance(candle.close - self._last_close)
        self._last_close = candle.close
        previous_rsi = self._previous_rsi
        self._previous_rsi = current_rsi
        if previous_rsi is None:
            return StrategyEvaluation(None, {"rsi": current_rsi})
        action = None
        if previous_rsi < self.oversold <= current_rsi:
            action = "buy"
        elif previous_rsi > self.overbought >= current_rsi:
            action = "sell"
        return StrategyEvaluation(action, {"rsi": current_rsi})


class MacdCrossEvaluator:
    """MACD선과 시그널선의 상향·하향 교차를 판정합니다."""

    def __init__(self, fast: int, slow: int, signal: int):
        if fast <= 0 or slow <= fast or signal <= 0:
            raise ValueError("MACD 기간은 0 < fast < slow, signal > 0 조건이어야 합니다.")
        self.fast = fast
        self.slow = slow
        self.signal = signal
        self.required_history = slow + signal + 100
        self._fast_ema: float | None = None
        self._slow_ema: float | None = None
        self._signal_ema: float | None = None
        self._previous_gap: float | None = None
        self._count = 0

    @staticmethod
    def _ema(previous: float, value: float, period: int) -> float:
        alpha = 2 / (period + 1)
        return value * alpha + previous * (1 - alpha)

    def _advance(self, close: float) -> tuple[float, float, float]:
        if self._fast_ema is None:
            self._fast_ema = self._slow_ema = close
            macd = 0.0
            self._signal_ema = 0.0
        else:
            self._fast_ema = self._ema(self._fast_ema, close, self.fast)
            self._slow_ema = self._ema(self._slow_ema, close, self.slow)
            macd = self._fast_ema - self._slow_ema
            self._signal_ema = self._ema(self._signal_ema or 0.0, macd, self.signal)
        self._count += 1
        return macd, self._signal_ema or 0.0, macd - (self._signal_ema or 0.0)

    def warmup(self, candles: list[Candle]) -> None:
        self._fast_ema = self._slow_ema = self._signal_ema = self._previous_gap = None
        self._count = 0
        for candle in candles:
            _, _, self._previous_gap = self._advance(candle.close)

    def update(self, candle: Candle) -> StrategyEvaluation | None:
        macd, signal_line, gap = self._advance(candle.close)
        if self._count < self.slow + self.signal:
            self._previous_gap = gap
            return None
        action = None
        if self._previous_gap is not None:
            if self._previous_gap <= 0 < gap:
                action = "buy"
            elif self._previous_gap >= 0 > gap:
                action = "sell"
        self._previous_gap = gap
        return StrategyEvaluation(action, {"macd": macd, "signal": signal_line, "histogram": gap})


class BollingerReentryEvaluator:
    """가격이 볼린저 밴드 밖에서 안으로 복귀하는 시점을 판정합니다."""

    def __init__(self, window: int, deviation: float):
        if window <= 1 or deviation <= 0:
            raise ValueError("볼린저 밴드 설정값이 올바르지 않습니다.")
        self.window = window
        self.deviation = deviation
        self.required_history = window + 1
        self._closes: deque[float] = deque(maxlen=self.required_history)

    def warmup(self, candles: list[Candle]) -> None:
        self._closes.clear()
        self._closes.extend(candle.close for candle in candles[-self.required_history :])

    def _bands(self, values: list[float]) -> tuple[float, float, float]:
        middle = _mean(values)
        standard_deviation = sqrt(sum((value - middle) ** 2 for value in values) / len(values))
        return middle, middle + self.deviation * standard_deviation, middle - self.deviation * standard_deviation

    def update(self, candle: Candle) -> StrategyEvaluation | None:
        self._closes.append(candle.close)
        if len(self._closes) < self.required_history:
            return None
        values = list(self._closes)
        _, previous_upper, previous_lower = self._bands(values[-self.window - 1 : -1])
        middle, upper, lower = self._bands(values[-self.window :])
        previous_close = values[-2]
        action = None
        if previous_close < previous_lower and candle.close >= lower:
            action = "buy"
        elif previous_close > previous_upper and candle.close <= upper:
            action = "sell"
        return StrategyEvaluation(action, {"middle": middle, "upper": upper, "lower": lower})


class DonchianBreakoutEvaluator:
    """현재 종가가 이전 N개 캔들의 고가·저가 채널을 돌파했는지 판정합니다."""

    def __init__(self, window: int):
        if window <= 1:
            raise ValueError("돈치안 채널 기간은 2 이상이어야 합니다.")
        self.window = window
        self.required_history = window
        self._candles: deque[Candle] = deque(maxlen=window)

    def warmup(self, candles: list[Candle]) -> None:
        self._candles.clear()
        self._candles.extend(candles[-self.window :])

    def update(self, candle: Candle) -> StrategyEvaluation | None:
        if len(self._candles) < self.window:
            self._candles.append(candle)
            return None
        upper = max(item.high for item in self._candles)
        lower = min(item.low for item in self._candles)
        action = "buy" if candle.close > upper else "sell" if candle.close < lower else None
        self._candles.append(candle)
        return StrategyEvaluation(action, {"upper": upper, "lower": lower})


class ManualHoldEvaluator:
    """미배정 자산: 신호를 생성하지 않습니다."""

    required_history = 0

    def warmup(self, candles: list[Candle]) -> None:
        pass

    def update(self, candle: Candle) -> StrategyEvaluation | None:
        return None


def create_evaluator(code: str, parameters: dict) -> StrategyEvaluator:
    """카탈로그 코드와 파라미터에 맞는 계산기를 생성합니다."""
    if code == "manual_hold_v1":
        return ManualHoldEvaluator()
    if code == "sma_cross_v1":
        return SmaCrossEvaluator(parameters["short_window"], parameters["long_window"])
    if code == "rsi_reversal_v1":
        return RsiReversalEvaluator(parameters["period"], parameters["oversold"], parameters["overbought"])
    if code == "macd_cross_v1":
        return MacdCrossEvaluator(parameters["fast"], parameters["slow"], parameters["signal"])
    if code == "bollinger_reentry_v1":
        return BollingerReentryEvaluator(parameters["window"], parameters["deviation"])
    if code == "donchian_breakout_v1":
        return DonchianBreakoutEvaluator(parameters["window"])
    raise ValueError(f"지원하지 않는 전략 코드입니다: {code}")

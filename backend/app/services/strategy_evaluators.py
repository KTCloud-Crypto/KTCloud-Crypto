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

class RsiMacdConfirmEvaluator:
    """RSI와 MACD가 동시에 같은 방향을 가리킬 때만 신호를 냅니다.

    단일 지표만 쓰면 가짜 신호(휩소)가 자주 나오는데, MACD가 실제로
    골든/데드크로스를 낸 순간에 RSI도 특정 구간에 있을 때만 신호를 인정해
    두 지표가 서로를 검증하도록 만든 전략입니다.
    """

    def __init__(
        self,
        rsi_period: int,
        macd_fast: int,
        macd_slow: int,
        macd_signal: int,
        rsi_buy_low: float = 30,
        rsi_buy_high: float = 50,
        rsi_sell_threshold: float = 70,
    ):
        self._rsi = RsiReversalEvaluator(rsi_period, 30, 70)
        self._macd = MacdCrossEvaluator(macd_fast, macd_slow, macd_signal)
        self.rsi_buy_low = rsi_buy_low
        self.rsi_buy_high = rsi_buy_high
        self.rsi_sell_threshold = rsi_sell_threshold
        self.required_history = max(self._rsi.required_history, self._macd.required_history)

    def warmup(self, candles: list[Candle]) -> None:
        self._rsi.warmup(candles)
        self._macd.warmup(candles)

    def update(self, candle: Candle) -> StrategyEvaluation | None:
        rsi_result = self._rsi.update(candle)
        macd_result = self._macd.update(candle)
        if rsi_result is None or macd_result is None:
            return None

        current_rsi = rsi_result.metrics.get("rsi")
        action = None
        if macd_result.action == "buy" and current_rsi is not None and self.rsi_buy_low <= current_rsi <= self.rsi_buy_high:
            action = "buy"
        elif macd_result.action == "sell" and current_rsi is not None and current_rsi >= self.rsi_sell_threshold:
            action = "sell"

        metrics = {"rsi": current_rsi or 0.0, **macd_result.metrics}
        return StrategyEvaluation(action, metrics)

class BollingerSqueezeBreakoutEvaluator:
    """밴드 폭이 평소보다 좁아졌다가(변동성 수축) 밴드를 돌파하는 순간을 판정합니다.

    기존 볼린저 회귀 전략과 반대로, 밴드 안으로 돌아오는 게 아니라
    수축 이후 밴드 밖으로 뚫고 나가는 순간을 신호로 삼습니다.
    """

    def __init__(
        self,
        window: int,
        deviation: float,
        squeeze_lookback: int,
        squeeze_ratio: float,
        squeeze_valid_candles: int,
    ):
        if window <= 1 or deviation <= 0:
            raise ValueError("볼린저 밴드 설정값이 올바르지 않습니다.")
        if squeeze_lookback <= 1 or not 0 < squeeze_ratio < 1 or squeeze_valid_candles <= 0:
            raise ValueError("수축 판정 설정값이 올바르지 않습니다.")
        self.window = window
        self.deviation = deviation
        self.squeeze_lookback = squeeze_lookback
        self.squeeze_ratio = squeeze_ratio
        self.squeeze_valid_candles = squeeze_valid_candles
        self.required_history = window + squeeze_lookback + 1
        self._closes: deque[float] = deque(maxlen=self.required_history)
        self._widths: deque[float] = deque(maxlen=squeeze_lookback)
        self._squeeze_countdown = 0

    def _bands(self, values: list[float]) -> tuple[float, float, float]:
        middle = _mean(values)
        standard_deviation = sqrt(sum((value - middle) ** 2 for value in values) / len(values))
        return middle, middle + self.deviation * standard_deviation, middle - self.deviation * standard_deviation

    def warmup(self, candles: list[Candle]) -> None:
        self._closes.clear()
        self._widths.clear()
        self._squeeze_countdown = 0
        history = [candle.close for candle in candles[-self.required_history :]]
        self._closes.extend(history)
        for index in range(self.window, len(history)):
            window_values = history[index - self.window : index]
            middle, upper, lower = self._bands(window_values)
            if middle:
                self._widths.append((upper - lower) / middle)

    def update(self, candle: Candle) -> StrategyEvaluation | None:
        self._closes.append(candle.close)
        if len(self._closes) < self.required_history:
            return None

        values = list(self._closes)
        _, previous_upper, previous_lower = self._bands(values[-self.window - 1 : -1])
        middle, upper, lower = self._bands(values[-self.window :])
        previous_close = values[-2]

        width_ratio = (upper - lower) / middle if middle else 0.0
        average_width = _mean(list(self._widths)) if self._widths else width_ratio
        self._widths.append(width_ratio)

        if average_width and width_ratio <= average_width * self.squeeze_ratio:
            self._squeeze_countdown = self.squeeze_valid_candles
        elif self._squeeze_countdown > 0:
            self._squeeze_countdown -= 1

        action = None
        if self._squeeze_countdown > 0:
            if previous_close <= previous_upper and candle.close > upper:
                action = "buy"
                self._squeeze_countdown = 0
            elif previous_close >= previous_lower and candle.close < lower:
                action = "sell"
                self._squeeze_countdown = 0

        return StrategyEvaluation(action, {"middle": middle, "upper": upper, "lower": lower, "width_ratio": width_ratio})

class VolatilityBreakoutEvaluator:
    """전일 변동폭에 K값을 곱한 목표가를 당일 돌파하면 매수합니다.

    목표가 = 오늘 시가 + (전일 고가 - 전일 저가) × K
    새 거래일(UTC 자정)이 시작되면 전날 포지션을 정리하도록 매도 신호를 냅니다.
    """

    _DAY_MS = 24 * 60 * 60 * 1000

    def __init__(self, k: float, lookback_candles: int = 300):
        if not 0 < k < 1:
            raise ValueError("K값은 0과 1 사이여야 합니다.")
        self.k = k
        self.required_history = lookback_candles
        self._day_index: int | None = None
        self._today_open: float | None = None
        self._current_day_high: float | None = None
        self._current_day_low: float | None = None
        self._prev_day_high: float | None = None
        self._prev_day_low: float | None = None
        self._target: float | None = None
        self._triggered_today = False

    def _reset_day(self, candle: Candle, day_index: int) -> None:
        self._day_index = day_index
        self._today_open = candle.open
        self._current_day_high = candle.high
        self._current_day_low = candle.low
        self._triggered_today = False
        if self._prev_day_high is not None and self._prev_day_low is not None:
            self._target = self._today_open + (self._prev_day_high - self._prev_day_low) * self.k
        else:
            self._target = None

    def warmup(self, candles: list[Candle]) -> None:
        self._day_index = None
        self._today_open = None
        self._current_day_high = None
        self._current_day_low = None
        self._prev_day_high = None
        self._prev_day_low = None
        self._target = None
        self._triggered_today = False
        for candle in candles:
            day_index = candle.open_time_ms // self._DAY_MS
            if self._day_index is None:
                self._day_index = day_index
                self._today_open = candle.open
                self._current_day_high = candle.high
                self._current_day_low = candle.low
                continue
            if day_index != self._day_index:
                self._prev_day_high = self._current_day_high
                self._prev_day_low = self._current_day_low
                self._reset_day(candle, day_index)
                continue
            self._current_day_high = max(self._current_day_high, candle.high)
            self._current_day_low = min(self._current_day_low, candle.low)

    def update(self, candle: Candle) -> StrategyEvaluation | None:
        day_index = candle.open_time_ms // self._DAY_MS
        if self._day_index is None:
            self._day_index = day_index
            self._today_open = candle.open
            self._current_day_high = candle.high
            self._current_day_low = candle.low
            return None

        if day_index != self._day_index:
            self._prev_day_high = self._current_day_high
            self._prev_day_low = self._current_day_low
            self._reset_day(candle, day_index)
            return StrategyEvaluation("sell", {"target": self._target or 0.0, "today_open": self._today_open or 0.0})

        self._current_day_high = max(self._current_day_high, candle.high)
        self._current_day_low = min(self._current_day_low, candle.low)

        action = None
        if self._target is not None and not self._triggered_today and candle.close >= self._target:
            action = "buy"
            self._triggered_today = True

        return StrategyEvaluation(action, {"target": self._target or 0.0, "today_open": self._today_open or 0.0})    
    

def create_evaluator(code: str, parameters: dict) -> StrategyEvaluator:
    """카탈로그 코드와 파라미터에 맞는 계산기를 생성합니다."""
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
    if code == "rsi_macd_confirm_v1":
        return RsiMacdConfirmEvaluator(
            parameters["rsi_period"],
            parameters["macd_fast"],
            parameters["macd_slow"],
            parameters["macd_signal"],
            parameters.get("rsi_buy_low", 30),
            parameters.get("rsi_buy_high", 50),
            parameters.get("rsi_sell_threshold", 70),
        )
    if code == "bollinger_squeeze_breakout_v1":
        return BollingerSqueezeBreakoutEvaluator(
            parameters["window"],
            parameters["deviation"],
            parameters["squeeze_lookback"],
            parameters["squeeze_ratio"],
            parameters["squeeze_valid_candles"],
        )
    if code == "volatility_breakout_v1":
        return VolatilityBreakoutEvaluator(parameters["k"])
    raise ValueError(f"지원하지 않는 전략 코드입니다: {code}")

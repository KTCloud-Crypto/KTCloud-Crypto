from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.metrics import STRATEGY_SIGNALS
from app.messaging.strategy_events import enqueue_strategy_signal_created
from app.models.strategy import Strategy, SupportedMarket, UserStrategy
from app.models.strategy_signal import StrategyRuntime, StrategySignal
from app.market_data import Candle, CandleBuilder, TradeTick, fetch_completed_minute_candles
from app.strategy.strategy_evaluators import StrategyEvaluator, create_evaluator
from app.strategy.risk_exit import create_triggered_exit_signals

logger = logging.getLogger(__name__)
OFFICIAL_CANDLE_FETCH_ATTEMPTS = 4
OFFICIAL_CANDLE_RETRY_SECONDS = 0.5
OFFICIAL_CANDLE_RECOVERY_COUNT = 10


def _risk_exits(market: str, price: float):
    """작업 스레드 안에서 전용 DB 세션을 열어 손절·익절 신호를 생성합니다."""
    db = SessionLocal()
    try:
        return create_triggered_exit_signals(db, market, price)
    finally:
        db.close()


@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    """계산에 필요한 전략 정보와 사용자 선택 분봉을 묶은 불변 설정입니다."""

    id: int
    code: str
    market: str
    timeframe_minutes: int
    parameters: dict


def _active_definitions() -> list[StrategyDefinition]:
    """현재 한 명 이상이 활성화한 전략·분봉 조합만 DB에서 조회합니다."""
    db = SessionLocal()
    try:
        rows = (
            db.query(Strategy, SupportedMarket.code, UserStrategy.timeframe_minutes)
            .join(UserStrategy, UserStrategy.strategy_id == Strategy.id)
            .join(SupportedMarket, SupportedMarket.id == UserStrategy.market_id)
            .filter(Strategy.enabled.is_(True), UserStrategy.enabled.is_(True))
            .distinct(Strategy.id, SupportedMarket.code, UserStrategy.timeframe_minutes)
            .all()
        )
        return [
            StrategyDefinition(
                id=strategy.id,
                code=strategy.code,
                market=market,
                timeframe_minutes=timeframe_minutes,
                parameters=dict(strategy.parameters or {}),
            )
            for strategy, market, timeframe_minutes in rows
        ]
    finally:
        db.close()


def _save_evaluation(
    definition: StrategyDefinition,
    candle: Candle,
    action: str | None,
    metrics: dict[str, float],
) -> int | None:
    """최신 계산값을 갱신하고 확정 신호가 있으면 중복 없이 기록합니다."""
    db = SessionLocal()
    try:
        candle_open_time = datetime.utcfromtimestamp(candle.open_time_ms / 1000)
        runtime = (
            db.query(StrategyRuntime)
            .filter(
                StrategyRuntime.strategy_id == definition.id,
                StrategyRuntime.market == definition.market,
                StrategyRuntime.timeframe_minutes == definition.timeframe_minutes,
            )
            .first()
        )
        if runtime is None:
            runtime = StrategyRuntime(
                strategy_id=definition.id,
                market=candle.market,
                timeframe_minutes=definition.timeframe_minutes,
                candle_open_time=candle_open_time,
                close_price=candle.close,
                metrics=metrics,
                action=action,
                evaluated_at=datetime.utcnow(),
            )
            db.add(runtime)
        else:
            runtime.market = candle.market
            runtime.candle_open_time = candle_open_time
            runtime.close_price = candle.close
            runtime.metrics = metrics
            runtime.action = action
            runtime.evaluated_at = datetime.utcnow()
        db.commit()

        if action is None:
            return None

        signal = StrategySignal(
            strategy_id=definition.id,
            market=candle.market,
            timeframe_minutes=definition.timeframe_minutes,
            action=action,
            source="engine",
            candle_open_time=candle_open_time,
            close_price=candle.close,
            metrics=metrics,
        )
        db.add(signal)
        enqueue_strategy_signal_created(db, signal)
        db.commit()
        db.refresh(signal)
        return signal.id
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()


class StrategyEngine:
    """활성 전략을 준비하고 마감 캔들을 해당 계산기에 전달합니다."""

    def __init__(self):
        self._definitions: dict[tuple[str, str, int], StrategyDefinition] = {}
        self._evaluators: dict[tuple[str, str, int], StrategyEvaluator] = {}
        self._builders: dict[int, CandleBuilder] = {}
        self._last_processed_candle: dict[tuple[str, str, int], int] = {}
        self._last_risk_check: dict[str, float] = {}

    async def refresh(self) -> None:
        """사용자 구독 변경과 카탈로그 파라미터 변경을 주기적으로 반영합니다."""
        definitions = await asyncio.to_thread(_active_definitions)
        desired = {(item.code, item.market, item.timeframe_minutes): item for item in definitions}

        for stale_key in set(self._definitions) - set(desired):
            self._definitions.pop(stale_key, None)
            self._evaluators.pop(stale_key, None)
            self._last_processed_candle.pop(stale_key, None)

        for key, definition in desired.items():
            if self._definitions.get(key) == definition:
                continue

            evaluator = create_evaluator(definition.code, definition.parameters)
            candles = await fetch_completed_minute_candles(
                market=definition.market,
                interval_minutes=definition.timeframe_minutes,
                count=evaluator.required_history,
            )
            evaluator.warmup(candles)
            self._definitions[key] = definition
            self._evaluators[key] = evaluator
            self._last_processed_candle[key] = candles[-1].open_time_ms if candles else -1
            self._builders.setdefault(
                definition.timeframe_minutes,
                CandleBuilder(definition.timeframe_minutes, self.on_candle_close),
            )
            logger.info(
                "Strategy warmed up: code=%s timeframe=%sm candles=%s",
                definition.code,
                definition.timeframe_minutes,
                len(candles),
            )

    async def on_trade(self, tick: TradeTick) -> None:
        """실시간 체결 tick을 현재 사용 중인 모든 분봉 생성기에 전달합니다."""
        for builder in tuple(self._builders.values()):
            await builder.on_trade(tick)
        # 체결 tick마다 DB를 조회하지 않도록 종목별 2초 간격으로 손절·익절을 평가합니다.
        now = time.monotonic()
        if now - self._last_risk_check.get(tick.market, 0) < 2:
            return
        self._last_risk_check[tick.market] = now
        exits = await asyncio.to_thread(_risk_exits, tick.market, tick.price)
        if exits:
            logger.info(
                "Risk exit signals queued: market=%s count=%s",
                tick.market,
                len(exits),
            )

    async def _fetch_official_candles(self, candidate: Candle) -> list[Candle]:
        """후보 구간까지의 Upbit 마감 봉을 조회하며 일시 장애를 내부에서 흡수합니다."""
        last_error: Exception | None = None
        for attempt in range(OFFICIAL_CANDLE_FETCH_ATTEMPTS):
            try:
                candles = await fetch_completed_minute_candles(
                    market=candidate.market,
                    interval_minutes=candidate.interval_minutes,
                    count=OFFICIAL_CANDLE_RECOVERY_COUNT,
                )
            except Exception as error:
                last_error = error
                candles = []

            if any(item.open_time_ms == candidate.open_time_ms for item in candles):
                return sorted(
                    (
                        item
                        for item in candles
                        if item.open_time_ms <= candidate.open_time_ms
                    ),
                    key=lambda item: item.open_time_ms,
                )
            if attempt < OFFICIAL_CANDLE_FETCH_ATTEMPTS - 1:
                await asyncio.sleep(OFFICIAL_CANDLE_RETRY_SECONDS)
        logger.warning(
            "Completed candle unavailable: market=%s timeframe=%sm open_time_ms=%s error=%s",
            candidate.market,
            candidate.interval_minutes,
            candidate.open_time_ms,
            type(last_error).__name__ if last_error else "not_published",
        )
        return []

    async def on_candle_close(self, candle: Candle) -> None:
        """Upbit의 공식 마감 봉을 계산하고 확정 신호를 실행 단계로 전달합니다."""
        matching_keys = [
            key
            for key, definition in tuple(self._definitions.items())
            if definition.market == candle.market
            and definition.timeframe_minutes == candle.interval_minutes
        ]
        if not matching_keys:
            return

        official_candles = await self._fetch_official_candles(candle)
        if not official_candles:
            return

        for key in matching_keys:
            definition = self._definitions.get(key)
            evaluator = self._evaluators.get(key)
            if definition is None or evaluator is None:
                continue
            for official_candle in official_candles:
                if official_candle.open_time_ms <= self._last_processed_candle.get(key, -1):
                    continue

                result = evaluator.update(official_candle)
                self._last_processed_candle[key] = official_candle.open_time_ms
                if result is None:
                    continue
                # 일시 장애로 뒤늦게 복구한 과거 봉은 지표 상태만 이어 붙입니다.
                # 오래된 신호로 현재 시점에 주문하는 것을 막기 위해 최신 후보 봉만 실행합니다.
                action = (
                    result.action
                    if official_candle.open_time_ms == candle.open_time_ms
                    else None
                )
                signal_id = await asyncio.to_thread(
                    _save_evaluation,
                    definition,
                    official_candle,
                    action,
                    result.metrics,
                )
                if action is not None and signal_id is not None:
                    STRATEGY_SIGNALS.labels(
                        definition.code, definition.market, action, "strategy"
                    ).inc()
                    logger.info(
                        "Strategy signal recorded: code=%s timeframe=%sm action=%s close=%s metrics=%s",
                        definition.code,
                        definition.timeframe_minutes,
                        action,
                        official_candle.close,
                        result.metrics,
                    )
                    logger.info("Strategy signal queued: signal_id=%s", signal_id)

    async def refresh_loop(self, stop_event: asyncio.Event) -> None:
        """워커 종료 요청 전까지 전략 구독 설정을 주기적으로 다시 읽습니다."""
        while not stop_event.is_set():
            await self.refresh()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=settings.strategy_refresh_seconds)
            except asyncio.TimeoutError:
                pass

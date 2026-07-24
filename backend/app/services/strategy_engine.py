from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.strategy import Strategy, SupportedMarket, UserStrategy
from app.models.strategy_signal import StrategyRuntime, StrategySignal
from app.services.candles import Candle, CandleBuilder
from app.services.market_history import fetch_completed_minute_candles
from app.services.market_stream import TradeTick
from app.services.signal_dispatcher import dispatch_signal
from app.services.strategy_evaluators import StrategyEvaluator, create_evaluator
from app.services.risk_exit import create_triggered_exit_signals

logger = logging.getLogger(__name__)


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
        self._last_risk_check: dict[str, float] = {}

    async def refresh(self) -> None:
        """사용자 구독 변경과 카탈로그 파라미터 변경을 주기적으로 반영합니다."""
        definitions = await asyncio.to_thread(_active_definitions)
        desired = {(item.code, item.market, item.timeframe_minutes): item for item in definitions}

        for stale_key in set(self._definitions) - set(desired):
            self._definitions.pop(stale_key, None)
            self._evaluators.pop(stale_key, None)

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
        for exit_signal in exits:
            await dispatch_signal(
                exit_signal.signal_id,
                user_id=exit_signal.user_id,
                mode=exit_signal.mode,
            )

    async def on_candle_close(self, candle: Candle) -> None:
        """마감 캔들을 계산하고 확정 신호를 사용자별 실행 단계로 전달합니다."""
        for key, definition in tuple(self._definitions.items()):
            if definition.market != candle.market or definition.timeframe_minutes != candle.interval_minutes:
                continue

            result = self._evaluators[key].update(candle)
            if result is None:
                continue
            signal_id = await asyncio.to_thread(
                _save_evaluation,
                definition,
                candle,
                result.action,
                result.metrics,
            )
            if result.action is not None and signal_id is not None:
                logger.info(
                    "Strategy signal recorded: code=%s timeframe=%sm action=%s close=%s metrics=%s",
                    definition.code,
                    definition.timeframe_minutes,
                    result.action,
                    candle.close,
                    result.metrics,
                )
                execution_count = await dispatch_signal(signal_id)
                logger.info("Strategy signal dispatched: signal_id=%s executions=%s", signal_id, execution_count)

    async def refresh_loop(self, stop_event: asyncio.Event) -> None:
        """워커 종료 요청 전까지 전략 구독 설정을 주기적으로 다시 읽습니다."""
        while not stop_event.is_set():
            await self.refresh()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=settings.strategy_refresh_seconds)
            except asyncio.TimeoutError:
                pass

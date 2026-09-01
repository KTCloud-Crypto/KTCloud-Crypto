from __future__ import annotations

from typing import Literal
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.market_data import get_current_price
from app.models.api_key import ApiKey
from app.models.strategy import Strategy, SupportedMarket, UserStrategy
from app.models.strategy_signal import TradingExecutionRequest
from app.models.user import User
from app.portfolio.strategy_positions import load_strategy_position
from app.trading.execution_preflight import MIN_KRW_ORDER
from app.identity import SimpleRateLimiter
from app.trading.manual_commands import enqueue_manual_liquidation


trade_action_limiter = SimpleRateLimiter(window_seconds=60, max_requests=10)


def _require_live_api_key(db: Session, user_id: int, mode: str) -> None:
    if mode != "live":
        return
    if db.query(ApiKey.id).filter(ApiKey.user_id == user_id).first() is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="실전투자를 사용하려면 먼저 Upbit API Key를 연결해 주세요.",
        )


def _enabled_strategy_or_404(db: Session, strategy_id: int) -> Strategy:
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id, Strategy.enabled.is_(True)).first()
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="전략을 찾을 수 없습니다.")
    return strategy


def _market_or_404(db: Session, market: str) -> SupportedMarket:
    selected_market = db.query(SupportedMarket).filter(
        SupportedMarket.code == market.upper(), SupportedMarket.enabled.is_(True)
    ).first()
    if selected_market is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="지원하지 않는 종목입니다.")
    return selected_market


def _has_open_position(db: Session, subscription: UserStrategy) -> bool:
    return load_strategy_position(db, subscription.id, subscription.mode).volume > 0


async def request_manual_sell(
    db: Session,
    *,
    user: User,
    strategy_id: int,
    mode: Literal["simulated", "live"],
    market: str,
    metric_key: str = "manual_price",
) -> tuple[TradingExecutionRequest, UserStrategy]:
    _require_live_api_key(db, user.id, mode)
    if user.execution_mode != mode:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="현재 선택한 투자 모드와 요청한 전략 모드가 다릅니다.",
        )
    strategy = _enabled_strategy_or_404(db, strategy_id)
    selected_market = _market_or_404(db, market)
    subscription = db.query(UserStrategy).filter(
        UserStrategy.user_id == user.id,
        UserStrategy.strategy_id == strategy.id,
        UserStrategy.market_id == selected_market.id,
        UserStrategy.mode == mode,
    ).first()
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="전략 설정을 찾을 수 없습니다.")
    if not _has_open_position(db, subscription):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="매도할 포지션이 없습니다.")
    price = await get_current_price(selected_market.code)
    execution_request = TradingExecutionRequest(
        idempotency_key=str(uuid4()),
        user_strategy_id=subscription.id,
        user_id=user.id,
        mode=mode,
        action="sell",
        market=selected_market.code,
        source="manual",
        reference_price=price,
    )
    db.add(execution_request)
    enqueue_manual_liquidation(db, execution_request)
    db.commit()
    db.refresh(execution_request)
    return execution_request, subscription


async def request_liquidate_all(
    db: Session,
    *,
    user: User,
    mode: Literal["simulated", "live"],
) -> list[TradingExecutionRequest]:
    _require_live_api_key(db, user.id, mode)
    if user.execution_mode != mode:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="현재 선택한 투자 모드와 요청한 모드가 다릅니다.")
    subscriptions = (
        db.query(UserStrategy)
        .filter(UserStrategy.user_id == user.id, UserStrategy.mode == mode)
        .all()
    )
    requests: list[TradingExecutionRequest] = []
    for subscription in subscriptions:
        if not _has_open_position(db, subscription):
            continue
        strategy = _enabled_strategy_or_404(db, subscription.strategy_id)
        market = db.get(SupportedMarket, subscription.market_id)
        if market is None:
            continue
        try:
            price = await get_current_price(market.code)
        except ValueError:
            continue
        execution_request = TradingExecutionRequest(
            idempotency_key=str(uuid4()),
            user_strategy_id=subscription.id,
            user_id=user.id,
            mode=mode,
            action="sell",
            market=market.code,
            source="manual",
            reference_price=price,
        )
        db.add(execution_request)
        enqueue_manual_liquidation(db, execution_request)
        db.commit()
        db.refresh(execution_request)
        requests.append(execution_request)
    return requests


async def request_telegram_liquidations(
    db: Session,
    *,
    user: User,
    subscription_ids: list[int],
) -> tuple[int, list[str]]:
    requested = 0
    failures: list[str] = []
    subscriptions = (
        db.query(UserStrategy, Strategy, SupportedMarket)
        .join(Strategy, Strategy.id == UserStrategy.strategy_id)
        .join(SupportedMarket, SupportedMarket.id == UserStrategy.market_id)
        .filter(UserStrategy.user_id == user.id, UserStrategy.id.in_(subscription_ids))
        .all()
    )
    for subscription, strategy, market in subscriptions:
        if not _has_open_position(db, subscription):
            continue
        try:
            await request_manual_sell(
                db,
                user=user,
                strategy_id=strategy.id,
                mode=subscription.mode,
                market=market.code,
                metric_key="telegram_manual_price",
            )
            requested += 1
        except (HTTPException, ValueError):
            failures.append(strategy.name)
    return requested, failures

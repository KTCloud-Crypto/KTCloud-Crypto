from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.audit import record_security_event
from app.core.database import get_db
from app.core.metrics import STRATEGY_SIGNALS
from app.identity.dependencies import get_current_user
from app.models.position_sync import PositionSyncAdjustment
from app.models.strategy import Strategy, UserStrategy
from app.models.strategy_signal import StrategyExecution, StrategySignal
from app.models.user import User
from app.portfolio.strategy_positions import execution_trade_details
from app.schemas.strategies import StrategyExecutionOut, StrategyTestSignalOut
from app.trading.manual_liquidation import (
    request_liquidate_all,
    request_manual_sell,
    request_telegram_liquidations,
    trade_action_limiter,
)


router = APIRouter(prefix="/strategies", tags=["Trading"])
internal_router = APIRouter(prefix="/internal/trading", tags=["Trading Internal"])


@router.get("/executions", response_model=list[StrategyExecutionOut])
def list_strategy_executions(
    mode: Literal["simulated", "live"] = Query("simulated"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[StrategyExecutionOut]:
    history_rows = (
        db.query(StrategyExecution, StrategySignal.source, Strategy.code)
        .outerjoin(StrategySignal, StrategySignal.id == StrategyExecution.signal_id)
        .join(UserStrategy, UserStrategy.id == StrategyExecution.user_strategy_id)
        .join(Strategy, Strategy.id == UserStrategy.strategy_id)
        .filter(StrategyExecution.user_id == current_user.id, StrategyExecution.mode == mode,
                or_(StrategySignal.id.is_(None), StrategySignal.source != "external_sync"),
                Strategy.code != "manual_hold_v1")
        .order_by(StrategyExecution.created_at, StrategyExecution.id).all()
    )
    details = execution_trade_details(
        [execution for execution, source, code in history_rows if source != "external_sync" and code != "manual_hold_v1"],
        db.query(PositionSyncAdjustment).join(UserStrategy, UserStrategy.id == PositionSyncAdjustment.user_strategy_id)
        .join(Strategy, Strategy.id == UserStrategy.strategy_id)
        .filter(PositionSyncAdjustment.user_id == current_user.id,
                PositionSyncAdjustment.action.in_(["deduct", "sell"]), Strategy.code != "manual_hold_v1").all()
        if mode == "live" else [],
    )
    rows = (
        db.query(StrategyExecution, Strategy, StrategySignal)
        .join(UserStrategy, UserStrategy.id == StrategyExecution.user_strategy_id)
        .join(Strategy, Strategy.id == UserStrategy.strategy_id)
        .outerjoin(StrategySignal, StrategySignal.id == StrategyExecution.signal_id)
        .filter(StrategyExecution.user_id == current_user.id, StrategyExecution.mode == mode,
                or_(StrategySignal.id.is_(None), StrategySignal.source != "external_sync"),
                Strategy.code != "manual_hold_v1")
        .order_by(StrategyExecution.created_at.desc()).limit(100).all()
    )
    return [StrategyExecutionOut(
        id=execution.id, strategy_name=strategy.name, strategy_code=strategy.code,
        action=execution.action, market=execution.market, mode=execution.mode, status=execution.status,
        price=execution.price, order_amount=execution.order_amount, order_volume=execution.order_volume,
        executed_volume=execution.executed_volume, average_price=execution.average_price, paid_fee=execution.paid_fee,
        entry_price=(details.get(execution.id).entry_price if details.get(execution.id) else None),
        transaction_amount=(details.get(execution.id).transaction_amount if details.get(execution.id) else None),
        realized_profit_loss=(details.get(execution.id).realized_profit_loss if details.get(execution.id) else None),
        error_message=execution.error_message, notification_sent=execution.notification_sent,
        exit_reason={"stop_loss": "손절", "take_profit": "목표 수익률", "manual": "수동 매도"}.get(signal.source if signal else "manual"),
        created_at=execution.created_at,
    ) for execution, strategy, signal in rows]


@router.post("/liquidate-all", response_model=list[StrategyTestSignalOut])
async def liquidate_all_positions(request: Request, mode: Literal["simulated", "live"] = Query("simulated"), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[StrategyTestSignalOut]:
    if not trade_action_limiter.allow(f"user:{current_user.id}:liquidate-all"):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="요청이 너무 많아 잠시 후 다시 시도해 주세요.")
    requests = await request_liquidate_all(db, user=current_user, mode=mode)
    record_security_event(db, "positions_liquidated", "success", actor_user_id=current_user.id,
                          resource_type="portfolio", resource_id=str(current_user.id), request=request,
                          metadata={"mode": mode, "request_count": len(requests)})
    return [StrategyTestSignalOut(signal_id=item.id, execution_count=1, action="sell", market=item.market, price=item.reference_price) for item in requests]


@router.post("/{strategy_id}/manual-sell", response_model=StrategyTestSignalOut)
async def create_manual_sell(strategy_id: int, request: Request, mode: Literal["simulated", "live"] = Query("simulated"), market: str = Query("KRW-BTC"), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> StrategyTestSignalOut:
    if not trade_action_limiter.allow(f"user:{current_user.id}:manual-sell"):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="요청이 너무 많아 잠시 후 다시 시도해 주세요.")
    execution_request, subscription = await request_manual_sell(db, user=current_user, strategy_id=strategy_id, mode=mode, market=market)
    strategy = db.get(Strategy, strategy_id)
    record_security_event(db, "position_manual_sell", "success", actor_user_id=current_user.id,
                          resource_type="user_strategy", resource_id=str(subscription.id), request=request,
                          metadata={"strategy_id": strategy_id, "market": execution_request.market, "mode": mode})
    return StrategyTestSignalOut(signal_id=execution_request.id, execution_count=1, action="sell", market=execution_request.market, price=execution_request.reference_price)


@internal_router.post("/users/{user_id}/manual-liquidations")
async def telegram_manual_liquidations(user_id: int, subscription_ids: list[int], db: Session = Depends(get_db)) -> dict[str, object]:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")
    requested, failures = await request_telegram_liquidations(db, user=user, subscription_ids=subscription_ids)
    return {"requested": requested, "failures": failures}

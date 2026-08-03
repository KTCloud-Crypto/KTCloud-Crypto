from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
 
from app.api.auth import get_current_user
from app.core.database import get_db
from app.core.config import settings
from app.models.api_key import ApiKey
from app.models.paper_account import PaperAccount
from app.models.strategy import Strategy, SupportedMarket, UserStrategy
from app.models.user import User
from app.models.strategy_signal import StrategyExecution, StrategyRuntime, StrategySignal
from app.schemas.strategies import (
    StrategyOut,
    StrategyExecutionOut,
    StrategyPositionOut,
    StrategySignalOut,
    StrategySubscriptionIn,
    SupportedMarketOut,
    StrategyTestSignalIn,
    StrategyTestSignalOut,
    ReservedStrategyOut,
)
from app.services.signal_dispatcher import dispatch_signal
from app.services.strategy_allocation import (
    allocated_ratio,
    available_for_order,
    reserved_amount,
)
from app.services.execution_preflight import MIN_KRW_ORDER, available_krw_balance
from app.services.strategy_positions import calculate_position
from app.services.execution_history import execution_trade_details
from app.services.upbit_service import get_current_price
 
router = APIRouter(prefix="/strategies", tags=["Strategies"])
ALLOWED_TIMEFRAMES = [1, 3, 5, 10, 30, 60, 240]
 
 
def _free_cash(
    db: Session,
    user_id: int,
    mode: str,
    exclude_subscription_id: int | None = None,
    reserve_fee: bool = True,
) -> Decimal | None:
    """다른 전략이 확보한 예산과 매수 수수료 여유분을 뺀 주문 가능 현금입니다.
 
    보유 중인 포지션은 이미 코인으로 바뀐 자산이므로 계산에 넣지 않습니다.
    실전인데 API 키가 없거나 잔고 조회에 실패하면 None을 반환합니다.
    """
    if mode == "simulated":
        account = (
            db.query(PaperAccount).filter(PaperAccount.user_id == user_id).first()
        )
        cash = Decimal(str(account.cash_balance)) if account else Decimal("0")
    else:
        api_key = db.query(ApiKey).filter(ApiKey.user_id == user_id).first()
        if api_key is None:
            return None
        try:
            cash = available_krw_balance(api_key)
        except ValueError:
            return None
 
    already_reserved = reserved_amount(
        db,
        user_id,
        mode,
        exclude_subscription_id=exclude_subscription_id,
    )
    return available_for_order(cash, already_reserved, reserve_fee=reserve_fee)
 
 
def _snapshot_budget(
    db: Session,
    user_id: int,
    mode: str,
    invest_ratio: float,
    exclude_subscription_id: int | None = None,
) -> float | None:
    """구독 시점의 자유 현금에 비율을 적용해 주문 예산을 확정합니다.
 
    실전인데 잔고를 조회할 수 없으면 None을 반환하며, 이 경우 첫 매수
    시점의 현금으로 산정합니다.
    """
    free_cash = _free_cash(db, user_id, mode, exclude_subscription_id)
    if free_cash is None:
        return None
    # free_cash에 수수료 여유분이 이미 반영돼 있으므로 여기서 또 빼지 않습니다.
    return float(
        (free_cash * Decimal(str(invest_ratio))).quantize(
            Decimal("1"), rounding=ROUND_DOWN
        )
    )
 
def _validated_invest_amount(
    db: Session,
    user_id: int,
    mode: str,
    amount: float,
    exclude_subscription_id: int | None = None,
) -> float:
    """직접 입력한 주문 금액이 최소 금액과 주문 가능 현금 범위 안인지 검사합니다."""
    requested = Decimal(str(amount))
    if requested < MIN_KRW_ORDER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"주문 금액은 최소 {MIN_KRW_ORDER:,.0f}원 이상이어야 합니다.",
        )
 
    free_cash = _free_cash(db, user_id, mode, exclude_subscription_id)
    if free_cash is not None and requested > free_cash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"주문 금액이 주문 가능 금액({free_cash:,.0f}원)을 초과합니다. "
                "다른 전략이 확보한 금액을 제외한 현금까지만 배정할 수 있습니다."
            ),
        )
    return float(requested)
 
 
def _ratio_from_amount(
    db: Session,
    user_id: int,
    mode: str,
    amount: float,
    fallback: float,
    exclude_subscription_id: int | None = None,
) -> float:
    """금액으로 설정했을 때 화면에 표시할 비율을 역산합니다.
 
    invest_ratio는 예산 계산에 쓰이지 않고 표시 용도로만 남습니다.
    """
    free_cash = _free_cash(db, user_id, mode, exclude_subscription_id)
    if not free_cash or free_cash <= 0:
        return fallback
    derived = Decimal(str(amount)) / free_cash
    return float(min(Decimal("1"), derived))
 
 
def _enabled_strategy_or_404(db: Session, strategy_id: int) -> Strategy:
    """활성 전략을 조회하고 없으면 API 공통 404 응답을 생성합니다."""
    strategy = (
        db.query(Strategy)
        .filter(Strategy.id == strategy_id, Strategy.enabled.is_(True))
        .first()
    )
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="전략을 찾을 수 없습니다.")
    return strategy
 
 
def _market_or_404(db: Session, market: str) -> SupportedMarket:
    item = db.query(SupportedMarket).filter(
        SupportedMarket.code == market.upper(),
        SupportedMarket.enabled.is_(True),
    ).first()
    if item is None:
        raise HTTPException(status_code=404, detail="지원하지 않는 종목입니다.")
    return item
 
 
def _user_subscription(
    db: Session,
    user_id: int,
    strategy_id: int,
    market_id: int,
    mode: str,
) -> UserStrategy | None:
    """사용자와 전략의 1:1 구독 설정을 조회합니다."""
    return (
        db.query(UserStrategy)
        .filter(
            UserStrategy.user_id == user_id,
            UserStrategy.strategy_id == strategy_id,
            UserStrategy.market_id == market_id,
            UserStrategy.mode == mode,
        )
        .first()
    )
 
 
def _runtime_for(
    db: Session,
    strategy_id: int,
    market: str,
    timeframe_minutes: int,
) -> StrategyRuntime | None:
    """전략 카드에 표시할 해당 분봉의 최신 계산값을 조회합니다."""
    return (
        db.query(StrategyRuntime)
        .filter(
            StrategyRuntime.strategy_id == strategy_id,
            StrategyRuntime.market == market,
            StrategyRuntime.timeframe_minutes == timeframe_minutes,
        )
        .first()
    )
 
 
def _has_open_position(db: Session, subscription: UserStrategy) -> bool:
    """모드에 맞는 성공 체결 기록으로 해당 전략의 미청산 수량을 확인합니다."""
    success_statuses = (
        frozenset({"simulated_success"})
        if subscription.mode == "simulated"
        else frozenset({"success", "partially_filled"})
    )
    executions = (
        db.query(StrategyExecution)
        .filter(
            StrategyExecution.user_strategy_id == subscription.id,
            StrategyExecution.status.in_(success_statuses),
        )
        .order_by(StrategyExecution.created_at, StrategyExecution.id)
        .all()
    )
    return calculate_position(executions, success_statuses).volume > 0
 
 
def _strategy_out(
    strategy: Strategy,
    market: SupportedMarket,
    subscription: UserStrategy | None,
    runtime: StrategyRuntime | None = None,
    has_open_position: bool = False,
    free_cash: float | None = None,
) -> StrategyOut:
    return StrategyOut(
        id=strategy.id,
        code=strategy.code,
        name=strategy.name,
        description=strategy.description,
        market=market.code,
        market_name=market.display_name,
        timeframe_minutes=strategy.timeframe_minutes,
        parameters=strategy.parameters or {},
        default_invest_ratio=strategy.default_invest_ratio,
        selected=bool(subscription and subscription.enabled),
        paused=bool(subscription and subscription.paused),
        has_open_position=has_open_position,
        invest_ratio=(subscription.invest_ratio if subscription else 0.0),
        allocated_amount=subscription.allocated_amount if subscription else None,
        available_cash=free_cash,
        stop_loss_rate=subscription.stop_loss_rate if subscription else None,
        take_profit_rate=subscription.take_profit_rate if subscription else None,
        selected_timeframe_minutes=(subscription.timeframe_minutes if subscription else 0),
        allowed_timeframes=ALLOWED_TIMEFRAMES,
        last_evaluated_at=runtime.evaluated_at if runtime else None,
        last_close_price=runtime.close_price if runtime else None,
        last_metrics=runtime.metrics if runtime else {},
        last_action=runtime.action if runtime else None,
    )
 
 
@router.get("", response_model=list[StrategyOut])
def list_strategies(
    mode: Literal["simulated", "live"] = Query("simulated"),
    market: str = Query("KRW-BTC"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[StrategyOut]:
    selected_market = (
        db.query(SupportedMarket)
        .filter(
            SupportedMarket.code == market.upper(),
            SupportedMarket.enabled.is_(True),
        )
        .first()
    )
    if selected_market is None:
        raise HTTPException(status_code=404, detail="지원하지 않는 종목입니다.")
    strategies = (
        db.query(Strategy)
        .filter(Strategy.enabled.is_(True), Strategy.code != "manual_hold_v1")
        .order_by(Strategy.id)
        .all()
    )
    subscriptions = {
        item.strategy_id: item
        for item in db.query(UserStrategy).filter(
            UserStrategy.user_id == current_user.id,
            UserStrategy.market_id == selected_market.id,
            UserStrategy.mode == mode,
        ).all()
    }
    runtimes = {
        (item.strategy_id, item.market, item.timeframe_minutes): item
        for item in db.query(StrategyRuntime).all()
    }
    def _free_cash_for(strategy_id: int) -> float | None:
        # 이미 구독 중인 전략을 다시 열 때는, 그 전략이 이미 확보해둔 예약금까지
        # 포함해서 계산해야 합니다. 자기 자신이 갖고 있던 돈을 "남이 써버린 돈"처럼
        # 또 빼버리면 안 되니, 그 구독만 제외하고 자유 현금을 계산합니다.
        existing = subscriptions.get(strategy_id)
        exclude_id = existing.id if existing else None
        free_cash = _free_cash(db, current_user.id, mode, exclude_subscription_id=exclude_id)
        return float(free_cash) if free_cash is not None else None

    return [
        _strategy_out(
            strategy,
            selected_market,
            subscriptions.get(strategy.id),
            runtimes.get(
                (
                    strategy.id,
                    selected_market.code,
                    subscriptions[strategy.id].timeframe_minutes
                    if strategy.id in subscriptions
                    else strategy.timeframe_minutes,
                )
            ),
            has_open_position=(
                _has_open_position(db, subscriptions[strategy.id])
                if strategy.id in subscriptions else False
            ),
            free_cash=_free_cash_for(strategy.id),
        )
        for strategy in strategies
    ]
 
 
@router.get("/markets", response_model=list[SupportedMarketOut])
def list_supported_markets(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[SupportedMarketOut]:
    return [
        SupportedMarketOut(code=item.code, display_name=item.display_name)
        for item in db.query(SupportedMarket)
        .filter(SupportedMarket.enabled.is_(True))
        .order_by(SupportedMarket.sort_order, SupportedMarket.id)
        .all()
    ]
 
 
@router.get("/allocation")
def read_strategy_allocation(
    mode: Literal["simulated", "live"] = Query("simulated"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, float | int]:
    """모든 종목에 활성화된 전략 투자 비율 합계를 반환합니다."""
    active_count = (
        db.query(UserStrategy.id)
        .join(Strategy, UserStrategy.strategy_id == Strategy.id)
        .filter(
            UserStrategy.user_id == current_user.id,
            UserStrategy.mode == mode,
            UserStrategy.enabled.is_(True),
            Strategy.code != "manual_hold_v1",
        )
        .count()
    )
    return {
        "total_ratio": float(allocated_ratio(db, current_user.id, mode)),
        "active_count": active_count,
    }
 
 
@router.get("/signals", response_model=list[StrategySignalOut])
def list_strategy_signals(
    mode: Literal["simulated", "live"] = Query("simulated"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[StrategySignalOut]:
    """현재 사용자가 선택한 전략·분봉과 일치하는 최근 신호를 조회합니다."""
    rows = (
        db.query(StrategySignal, Strategy)
        .join(Strategy, Strategy.id == StrategySignal.strategy_id)
        .join(
            UserStrategy,
            (UserStrategy.strategy_id == StrategySignal.strategy_id)
            & (UserStrategy.timeframe_minutes == StrategySignal.timeframe_minutes),
        )
        .join(SupportedMarket, SupportedMarket.id == UserStrategy.market_id)
        .filter(
            UserStrategy.user_id == current_user.id,
            UserStrategy.mode == mode,
            UserStrategy.enabled.is_(True),
            SupportedMarket.code == StrategySignal.market,
        )
        .order_by(StrategySignal.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        StrategySignalOut(
            id=signal.id,
            strategy_name=strategy.name,
            strategy_code=strategy.code,
            market=signal.market,
            timeframe_minutes=signal.timeframe_minutes,
            action=signal.action,
            source=signal.source,
            close_price=signal.close_price,
            metrics=signal.metrics or {},
            candle_open_time=signal.candle_open_time,
            created_at=signal.created_at,
        )
        for signal, strategy in rows
    ]
 
 
@router.get("/positions", response_model=list[StrategyPositionOut])
def list_strategy_positions(
    mode: Literal["simulated", "live"] = Query("simulated"),
    market: str = Query("KRW-BTC"),
    all_markets: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[StrategyPositionOut]:
    """전략별 성공 체결 기록으로 현재 소유 수량과 평균 매수가를 계산합니다."""
    if all_markets:
        items = (
            db.query(Strategy, UserStrategy, SupportedMarket)
            .join(UserStrategy, UserStrategy.strategy_id == Strategy.id)
            .join(SupportedMarket, SupportedMarket.id == UserStrategy.market_id)
            .filter(
                UserStrategy.user_id == current_user.id,
                UserStrategy.mode == mode,
            )
            .order_by(SupportedMarket.sort_order, Strategy.id)
            .all()
        )
    else:
        selected_market = _market_or_404(db, market)
        strategies = db.query(Strategy).filter(Strategy.enabled.is_(True)).order_by(Strategy.id).all()
        subscriptions = {
            item.strategy_id: item
            for item in db.query(UserStrategy).filter(
                UserStrategy.user_id == current_user.id,
                UserStrategy.market_id == selected_market.id,
                UserStrategy.mode == mode,
            ).all()
        }
        items = [
            (strategy, subscriptions.get(strategy.id), selected_market)
            for strategy in strategies
        ]
    executions = (
        db.query(StrategyExecution)
        .filter(StrategyExecution.user_id == current_user.id)
        .order_by(StrategyExecution.created_at)
        .all()
    )
    by_subscription: dict[int, list[StrategyExecution]] = {}
    for execution in executions:
        by_subscription.setdefault(execution.user_strategy_id, []).append(execution)
 
    result = []
    for strategy, subscription, item_market in items:
        position = (
            calculate_position(
                by_subscription.get(subscription.id, []),
                frozenset({"success", "partially_filled"}),
            )
            if subscription else None
        )
        paper_position = (
            calculate_position(
                [
                    item
                    for item in by_subscription.get(subscription.id, [])
                    if item.status == "simulated_success"
                ],
                frozenset({"simulated_success"}),
            )
            if subscription
            else None
        )
        volume = position.volume if position else 0.0
        paper_volume = paper_position.volume if paper_position else 0.0
 
        # all_markets=true일 때는 보유량이 0인 전략은 제외
        if all_markets:
            if mode == "simulated" and paper_volume == 0:
                continue
            if mode == "live" and volume == 0:
                continue
 
        result.append(
            StrategyPositionOut(
                strategy_id=strategy.id,
                strategy_name=strategy.name,
                strategy_code=strategy.code,
                market=item_market.code,
                enabled=bool(subscription and subscription.enabled),
                timeframe_minutes=(
                    subscription.timeframe_minutes if subscription else strategy.timeframe_minutes
                ),
                invest_ratio=(
                    subscription.invest_ratio if subscription else strategy.default_invest_ratio
                ),
                volume=volume,
                average_buy_price=position.average_buy_price if position else None,
                status="holding" if volume > 0 else "flat",
                paper_volume=paper_position.volume if paper_position else 0,
                paper_average_buy_price=(
                    paper_position.average_buy_price if paper_position else None
                ),
                paper_status=(
                    "holding" if paper_position and paper_position.volume > 0 else "flat"
                ),
            )
        )
    return result
 
 
@router.get("/executions", response_model=list[StrategyExecutionOut])
def list_strategy_executions(
    mode: Literal["simulated", "live"] = Query("simulated"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[StrategyExecutionOut]:
    """모의 실행과 실주문 검사·체결 결과를 최근 순서로 조회합니다."""
    history = (
        db.query(StrategyExecution)
        .filter(
            StrategyExecution.user_id == current_user.id,
            StrategyExecution.mode == mode,
        )
        .order_by(StrategyExecution.created_at, StrategyExecution.id)
        .all()
    )
    trade_details = execution_trade_details(history)
    rows = (
        db.query(StrategyExecution, Strategy, StrategySignal)
        .join(UserStrategy, UserStrategy.id == StrategyExecution.user_strategy_id)
        .join(Strategy, Strategy.id == UserStrategy.strategy_id)
        .join(StrategySignal, StrategySignal.id == StrategyExecution.signal_id)
        .filter(
            StrategyExecution.user_id == current_user.id,
            StrategyExecution.mode == mode,
        )
        .order_by(StrategyExecution.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        StrategyExecutionOut(
            id=execution.id,
            strategy_name=strategy.name,
            strategy_code=strategy.code,
            action=execution.action,
            market=execution.market,
            mode=execution.mode,
            status=execution.status,
            price=execution.price,
            order_amount=execution.order_amount,
            order_volume=execution.order_volume,
            executed_volume=execution.executed_volume,
            average_price=execution.average_price,
            entry_price=trade_details[execution.id].entry_price,
            transaction_amount=trade_details[execution.id].transaction_amount,
            realized_profit_loss=trade_details[execution.id].realized_profit_loss,
            error_message=execution.error_message,
            notification_sent=execution.notification_sent,
            exit_reason=(
                {
                    "stop_loss": "손절",
                    "take_profit": "목표 수익률",
                    "manual": "수동 매도",
                }.get(signal.source)
            ),
            created_at=execution.created_at,
        )
        for execution, strategy, signal in rows
    ]
 
 
@router.put("/{strategy_id}/subscription", response_model=StrategyOut)
def update_subscription(
    strategy_id: int,
    payload: StrategySubscriptionIn,
    mode: Literal["simulated", "live"] = Query("simulated"),
    market: str = Query("KRW-BTC"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StrategyOut:
    # 같은 사용자의 동시 설정 요청도 예산 산정을 순서대로 처리합니다.
    db.query(User).filter(User.id == current_user.id).with_for_update().one()
    strategy = _enabled_strategy_or_404(db, strategy_id)
    selected_market = _market_or_404(db, market)
    subscription = _user_subscription(
        db, current_user.id, strategy.id, selected_market.id, mode
    )
    if payload.enabled:
        if payload.timeframe_minutes is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="전략을 활성화하려면 분봉을 설정한 후 저장해 주세요.",
            )
        if payload.invest_ratio is None and payload.invest_amount is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="전략을 활성화하려면 투자 비율 또는 주문 금액을 설정한 후 저장해 주세요.",
            )
    invest_ratio = (
        payload.invest_ratio
        if payload.invest_ratio is not None
        else subscription.invest_ratio if subscription else strategy.default_invest_ratio
    )
    timeframe_minutes = (
        payload.timeframe_minutes
        if payload.timeframe_minutes is not None
        else subscription.timeframe_minutes if subscription else strategy.timeframe_minutes
    )
    stop_loss_rate = (
        None if payload.stop_loss_rate == 0 else payload.stop_loss_rate
        if "stop_loss_rate" in payload.model_fields_set
        else subscription.stop_loss_rate if subscription else None
    )
    take_profit_rate = (
        None if payload.take_profit_rate == 0 else payload.take_profit_rate
        if "take_profit_rate" in payload.model_fields_set
        else subscription.take_profit_rate if subscription else None
    )
 
    if subscription is not None and _has_open_position(db, subscription):
        if not payload.enabled and not payload.force_disable:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="보유 중인 포지션을 먼저 매도한 후 전략 선택을 해제해 주세요.",
            )
        if timeframe_minutes != subscription.timeframe_minutes:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="보유 중인 포지션을 먼저 매도한 후 분봉을 변경해 주세요. 투자 비율은 변경할 수 있습니다.",
            )
 
    exclude_id = subscription.id if subscription else None
    # 금액을 직접 입력하면 그 금액이 곧 주문 예산이 되고, 비율은 표시용으로 역산합니다.
    amount_requested = payload.enabled and payload.invest_amount is not None
    if amount_requested:
        validated_amount = _validated_invest_amount(
            db,
            current_user.id,
            mode,
            payload.invest_amount,
            exclude_subscription_id=exclude_id,
        )
        invest_ratio = _ratio_from_amount(
            db,
            current_user.id,
            mode,
            validated_amount,
            fallback=invest_ratio,
            exclude_subscription_id=exclude_id,
        )
 
    if subscription is None:
        subscription = UserStrategy(
            user_id=current_user.id,
            strategy_id=strategy.id,
            market_id=selected_market.id,
            mode=mode,
            invest_ratio=invest_ratio,
            stop_loss_rate=stop_loss_rate,
            take_profit_rate=take_profit_rate,
            timeframe_minutes=timeframe_minutes,
            enabled=payload.enabled,
            allocated_amount=(
                validated_amount
                if amount_requested
                else _snapshot_budget(db, current_user.id, mode, invest_ratio)
                if payload.enabled
                else None
            ),
        )
        db.add(subscription)
    else:
        was_enabled = subscription.enabled
        ratio_changed = subscription.invest_ratio != invest_ratio
        subscription.enabled = payload.enabled
        # 웹에서 해제한 전략을 다시 선택하는 것은 명시적인 실행 재개로 봅니다.
        # 선택된 상태에서 설정만 저장할 때는 Telegram 일시정지를 유지합니다.
        if payload.enabled and not was_enabled:
            subscription.paused = False
        subscription.invest_ratio = invest_ratio
        subscription.stop_loss_rate = stop_loss_rate
        subscription.take_profit_rate = take_profit_rate
        subscription.timeframe_minutes = timeframe_minutes
 
        if amount_requested:
            subscription.allocated_amount = validated_amount
        elif payload.enabled and (ratio_changed or not was_enabled):
            # 새로 선택했거나 투자 비율을 바꾼 경우에만 예산을 다시 잡습니다.
            # 분봉이나 손절 설정만 바꿀 때는 기존 예산을 유지합니다.
            subscription.allocated_amount = _snapshot_budget(
                db,
                current_user.id,
                mode,
                invest_ratio,
                exclude_subscription_id=subscription.id,
            )
 
    db.commit()
    db.refresh(subscription)
    runtime = _runtime_for(
        db, strategy.id, selected_market.code, subscription.timeframe_minutes
    )
    free_cash = _free_cash(db, current_user.id, mode)
    return _strategy_out(
        strategy,
        selected_market,
        subscription,
        runtime,
        has_open_position=_has_open_position(db, subscription),
        free_cash=float(free_cash) if free_cash is not None else None,
    )
 
 
@router.post("/{strategy_id}/test-signal", response_model=StrategyTestSignalOut)
async def create_test_signal(
    strategy_id: int,
    payload: StrategyTestSignalIn,
    mode: Literal["simulated", "live"] = Query("simulated"),
    market: str = Query("KRW-BTC"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StrategyTestSignalOut:
    """개발 환경에서 현재 사용자에게만 수동 테스트 신호를 분배합니다."""
    if settings.environment.lower() not in {"development", "local", "test"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="운영 환경에서는 사용할 수 없습니다.")
 
    strategy = _enabled_strategy_or_404(db, strategy_id)
    selected_market = _market_or_404(db, market)
    if current_user.execution_mode != mode:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="현재 선택한 투자 모드와 요청한 전략 모드가 다릅니다.",
        )
    subscription = _user_subscription(
        db, current_user.id, strategy.id, selected_market.id, mode
    )
    if subscription is None or not subscription.enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="먼저 전략을 선택해 주세요.")
 
    price = await get_current_price(selected_market.code)
    signal = StrategySignal(
        strategy_id=strategy.id,
        market=selected_market.code,
        timeframe_minutes=subscription.timeframe_minutes,
        action=payload.action,
        source="test",
        candle_open_time=datetime.utcnow(),
        close_price=price,
        metrics={"test_price": price},
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
 
    execution_count = await dispatch_signal(
        signal.id,
        user_id=current_user.id,
        mode=mode,
    )
    return StrategyTestSignalOut(
        signal_id=signal.id,
        execution_count=execution_count,
        action=signal.action,
        market=signal.market,
        price=signal.close_price,
    )
 
 
@router.get("/reserved", response_model=list[ReservedStrategyOut])
def list_reserved_strategies(
    mode: Literal["simulated", "live"] = Query("simulated"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ReservedStrategyOut]:
    """구독됐지만 아직 매수 전(예산만 확보된) 전략을 전체 종목 기준으로 조회합니다."""
    subscriptions = (
        db.query(UserStrategy, Strategy, SupportedMarket)
        .join(Strategy, Strategy.id == UserStrategy.strategy_id)
        .join(SupportedMarket, SupportedMarket.id == UserStrategy.market_id)
        .filter(
            UserStrategy.user_id == current_user.id,
            UserStrategy.mode == mode,
            UserStrategy.enabled.is_(True),
            Strategy.code != "manual_hold_v1",
        )
        .all()
    )
 
    result: list[ReservedStrategyOut] = []
    for subscription, strategy, market in subscriptions:
        if _has_open_position(db, subscription):
            continue
        result.append(
            ReservedStrategyOut(
                id=strategy.id,
                name=strategy.name,
                market=market.code,
                market_name=market.display_name,
                invest_ratio=subscription.invest_ratio,
                allocated_amount=subscription.allocated_amount,
                timeframe_minutes=subscription.timeframe_minutes,
            )
        )
    return result
 
 
@router.post("/liquidate-all", response_model=list[StrategyTestSignalOut])
async def liquidate_all_positions(
    mode: Literal["simulated", "live"] = Query("simulated"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[StrategyTestSignalOut]:
    """현재 보유 중인 모든 전략의 포지션을 순회하며 한 번에 시장가로 매도합니다.
 
    구독을 해제하지 않고 매도만 하므로, 매도 후에도 다음 매수 신호가 오면
    다시 정상적으로 매매가 이어집니다. 포지션이 없는 전략은 건드리지 않습니다.
    """
    if current_user.execution_mode != mode:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="현재 선택한 투자 모드와 요청한 모드가 다릅니다.",
        )
 
    subscriptions = (
        db.query(UserStrategy, Strategy, SupportedMarket)
        .join(Strategy, Strategy.id == UserStrategy.strategy_id)
        .join(SupportedMarket, SupportedMarket.id == UserStrategy.market_id)
        .filter(
            UserStrategy.user_id == current_user.id,
            UserStrategy.mode == mode,
        )
        .all()
    )
 
    results: list[StrategyTestSignalOut] = []
    for subscription, strategy, market in subscriptions:
        if not _has_open_position(db, subscription):
            continue
 
        price = await get_current_price(market.code)
        signal = StrategySignal(
            strategy_id=strategy.id,
            market=market.code,
            timeframe_minutes=subscription.timeframe_minutes,
            action="sell",
            source="manual",
            candle_open_time=datetime.utcnow(),
            close_price=price,
            metrics={"manual_price": price},
        )
        db.add(signal)
        db.commit()
        db.refresh(signal)
 
        execution_count = await dispatch_signal(
            signal.id,
            user_id=current_user.id,
            mode=mode,
        )
        results.append(
            StrategyTestSignalOut(
                signal_id=signal.id,
                execution_count=execution_count,
                action="sell",
                market=market.code,
                price=price,
            )
        )
 
    return results
 
 
@router.post("/{strategy_id}/manual-sell", response_model=StrategyTestSignalOut)
async def create_manual_sell(
    strategy_id: int,
    mode: Literal["simulated", "live"] = Query("simulated"),
    market: str = Query("KRW-BTC"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StrategyTestSignalOut:
    """해당 전략이 소유한 포지션 전량을 기존 주문 경로로 수동 매도합니다."""
    if current_user.execution_mode != mode:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="현재 선택한 투자 모드와 요청한 전략 모드가 다릅니다.",
        )
    strategy = _enabled_strategy_or_404(db, strategy_id)
    selected_market = _market_or_404(db, market)
    subscription = _user_subscription(
        db, current_user.id, strategy.id, selected_market.id, mode
    )
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="전략 설정을 찾을 수 없습니다.")
    if not _has_open_position(db, subscription):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="매도할 포지션이 없습니다.")
 
    price = await get_current_price(selected_market.code)
    signal = StrategySignal(
        strategy_id=strategy.id,
        market=selected_market.code,
        timeframe_minutes=subscription.timeframe_minutes,
        action="sell",
        source="manual",
        candle_open_time=datetime.utcnow(),
        close_price=price,
        metrics={"manual_price": price},
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    execution_count = await dispatch_signal(
        signal.id,
        user_id=current_user.id,
        mode=mode,
    )
    return StrategyTestSignalOut(
        signal_id=signal.id,
        execution_count=execution_count,
        action="sell",
        market=selected_market.code,
        price=price,
    )

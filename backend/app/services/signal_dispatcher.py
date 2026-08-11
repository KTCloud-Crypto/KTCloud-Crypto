"""확정된 전략 신호를 사용자별 모의 실행 또는 실제 주문으로 분배합니다."""

from __future__ import annotations
 
import asyncio
import time
from dataclasses import dataclass
 
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from sqlalchemy.orm import Session
 
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.metrics import ORDER_DURATION, ORDERS, STRATEGY_EXECUTIONS
from app.models.api_key import ApiKey
from app.models.strategy import Strategy, SupportedMarket, UserStrategy
from app.models.strategy_signal import StrategyExecution, StrategyRuntime, StrategySignal
from app.models.trade import Trade
from app.models.user import User
from app.services.execution_preflight import (
    PreflightResult,
    validate_order_readiness,
    validate_sell_readiness,
)
from app.services.exchange_credentials import resolve_exchange_credentials
from app.services.live_order import LiveOrderResult, execute_market_buy, execute_market_sell
from app.services.strategy_positions import calculate_position
from app.services.paper_trading import execute_paper_order
from app.services.telegram import send_message
 
IN_FLIGHT_ORDER_STATUSES = frozenset({"ready", "submitted", "partially_filled", "uncertain"})
PAPER_IN_FLIGHT_STATUSES = frozenset({"simulated_pending"})
 
 
@dataclass(frozen=True, slots=True)
class ExecutionTarget:
    """한 전략 신호를 적용할 사용자와 사용자별 설정의 스냅샷."""
 
    signal_id: int
    user_strategy_id: int
    user_id: int
    strategy_name: str
    action: str
    market: str
    price: float
    invest_ratio: float
    allocated_amount: float | None
    execution_mode: str
    telegram_chat_id: str | None
    signal_source: str
    live_trading_enabled: bool
 
 
def _targets_for_signal(
    signal_id: int,
    user_id: int | None = None,
    mode: str | None = None,
) -> list[ExecutionTarget]:
    """신호의 전략·분봉을 선택하고 자동매매를 켠 사용자만 조회합니다."""
    db = SessionLocal()
    try:
        query = (
            db.query(StrategySignal, Strategy, UserStrategy, User)
            .join(Strategy, Strategy.id == StrategySignal.strategy_id)
            .join(UserStrategy, UserStrategy.strategy_id == Strategy.id)
            .join(SupportedMarket, SupportedMarket.id == UserStrategy.market_id)
            .join(User, User.id == UserStrategy.user_id)
            .filter(
                StrategySignal.id == signal_id,
                Strategy.enabled.is_(True),
                or_(UserStrategy.enabled.is_(True), StrategySignal.source == "manual"),
                UserStrategy.timeframe_minutes == StrategySignal.timeframe_minutes,
                SupportedMarket.code == StrategySignal.market,
                or_(User.bot_enabled.is_(True), StrategySignal.source == "manual"),
            )
        )
        if user_id is not None:
            query = query.filter(User.id == user_id)
        if mode is not None:
            query = query.filter(UserStrategy.mode == mode)
 
        return [
            ExecutionTarget(
                signal_id=signal.id,
                user_strategy_id=subscription.id,
                user_id=user.id,
                strategy_name=strategy.name,
                action=signal.action,
                market=signal.market,
                price=signal.close_price,
                invest_ratio=subscription.invest_ratio,
                allocated_amount=subscription.allocated_amount,
                execution_mode=subscription.mode,
                telegram_chat_id=user.telegram_chat_id,
                signal_source=signal.source,
                live_trading_enabled=user.live_trading_enabled,
            )
            for signal, strategy, subscription, user in query.all()
        ]
    finally:
        db.close()
 
 
def _remaining_strategy_volume(db: Session, user_strategy_id: int) -> float:
    """성공한 매수 체결량에서 매도 체결량을 빼 전략 소유 수량을 계산합니다."""
    executions = (
        db.query(StrategyExecution)
        .filter(
            StrategyExecution.user_strategy_id == user_strategy_id,
            StrategyExecution.status.in_(["success", "partially_filled"]),
        )
        .all()
    )
    return calculate_position(executions, frozenset({"success", "partially_filled"})).volume
 
 
def managed_live_positions_value(db: Session, user_id: int) -> float:
    """SignalTrade 실전 전략이 보유한 포지션만 최신 계산 가격으로 평가합니다."""
    subscriptions = db.query(UserStrategy).filter(
        UserStrategy.user_id == user_id,
        UserStrategy.mode == "live",
    ).all()
    total = 0.0
    for subscription in subscriptions:
        executions = (
            db.query(StrategyExecution)
            .filter(
                StrategyExecution.user_strategy_id == subscription.id,
                StrategyExecution.status.in_(["success", "partially_filled"]),
            )
            .all()
        )
        position = calculate_position(
            executions,
            frozenset({"success", "partially_filled"}),
        )
        if position.volume <= 0:
            continue
        runtime = (
            db.query(StrategyRuntime)
            .filter(
                StrategyRuntime.strategy_id == subscription.strategy_id,
                StrategyRuntime.market == (
                    db.query(SupportedMarket.code)
                    .filter(SupportedMarket.id == subscription.market_id)
                    .scalar_subquery()
                ),
                StrategyRuntime.timeframe_minutes == subscription.timeframe_minutes,
            )
            .first()
        )
        mark_price = runtime.close_price if runtime else position.average_buy_price
        total += position.volume * float(mark_price or 0)
    return total
 
 
def _has_pending_action(db: Session, target: ExecutionTarget) -> bool:
    """같은 사용자 전략의 동일 방향 주문이 선점 또는 접수 중인지 확인합니다."""
    return (
        db.query(StrategyExecution.id)
        .filter(
            StrategyExecution.user_strategy_id == target.user_strategy_id,
            StrategyExecution.action == target.action,
            StrategyExecution.status.in_(IN_FLIGHT_ORDER_STATUSES),
        )
        .first()
        is not None
    )
 
 
def _has_pending_paper_action(db: Session, target: ExecutionTarget) -> bool:
    """동일한 모의 전략 주문이 잔고 반영을 끝내기 전인지 확인합니다."""
    return (
        db.query(StrategyExecution.id)
        .filter(
            StrategyExecution.user_strategy_id == target.user_strategy_id,
            StrategyExecution.action == target.action,
            StrategyExecution.status.in_(PAPER_IN_FLIGHT_STATUSES),
        )
        .first()
        is not None
    )
 
 
def should_skip_live_signal(action: str, preflight: PreflightResult | None) -> bool:
    """포지션 상태상 정상적으로 무시할 실전 신호인지 구분합니다."""
    if preflight is None or preflight.ready:
        return False
    return preflight.reason == "이미 같은 방향의 주문이 접수 중입니다." or (
        action == "buy"
        and preflight.reason == "이 전략으로 보유 중인 수량이 있어 중복 매수를 차단했습니다."
    ) or (
        action == "sell"
        and preflight.reason == "이 전략으로 매수해 남아 있는 수량이 없습니다."
    )
 
 
def _prepare_live_execution(db: Session, target: ExecutionTarget) -> PreflightResult:
    """실제 주문 전에 중복 주문, 전략 수량, 거래소 잔고와 최소 금액을 검사합니다."""
    strategy_volume = _remaining_strategy_volume(db, target.user_strategy_id)
    api_key = db.query(ApiKey).filter(ApiKey.user_id == target.user_id).first()
 
    if _has_pending_action(db, target):
        return PreflightResult(False, None, "이미 같은 방향의 주문이 접수 중입니다.")
 
    if target.action == "buy":
        if strategy_volume > 0:
            return PreflightResult(
                False,
                None,
                "이 전략으로 보유 중인 수량이 있어 중복 매수를 차단했습니다.",
            )
        return validate_order_readiness(
            api_key=api_key,
            action="buy",
            market=target.market,
            reference_price=target.price,
            invest_ratio=target.invest_ratio,
            allocated_amount=target.allocated_amount,
        )
 
    if target.action == "sell":
        return validate_sell_readiness(
            api_key=api_key,
            market=target.market,
            reference_price=target.price,
            strategy_volume=strategy_volume,
        )
 
    return PreflightResult(False, None, "지원하지 않는 주문 방향입니다.")
 
 
def _create_execution(
    db: Session,
    target: ExecutionTarget,
    preflight: PreflightResult | None,
) -> StrategyExecution | None:
    """중복 분배를 DB 유일성 제약으로 차단하며 실행 레코드를 생성합니다."""
    skipped_live_signal = target.execution_mode == "live" and should_skip_live_signal(
        target.action,
        preflight,
    )
    execution = StrategyExecution(
        signal_id=target.signal_id,
        user_strategy_id=target.user_strategy_id,
        user_id=target.user_id,
        mode=target.execution_mode,
        action=target.action,
        market=target.market,
        status=(
            "simulated_pending"
            if target.execution_mode == "simulated"
            else "skipped" if skipped_live_signal
            else "ready" if preflight and preflight.ready else "validation_failed"
        ),
        price=target.price,
        order_amount=preflight.order_amount if preflight else None,
        order_volume=preflight.order_volume if preflight else None,
        error_message=preflight.reason if preflight else None,
    )
    db.add(execution)
    try:
        db.commit()
        db.refresh(execution)
        return execution
    except IntegrityError:
        db.rollback()
        return None
 
 
def _sync_allocated_amount(
    db: Session,
    target: ExecutionTarget,
    execution: StrategyExecution,
) -> None:
    """완전 체결된 실전 주문 결과를 전략 예산에 반영합니다.
 
    - 매수: 예산이 비어 있던 기존 구독이면 이번 주문금액으로 확정합니다.
    - 매도: 회수한 현금을 다음 매수 예산으로 넘겨 손익을 반영합니다.
 
    부분 체결(partially_filled)이나 미확정 상태는 금액이 확정되지 않았으므로
    기존 예산을 그대로 유지합니다.
    """
    if execution.status != "success":
        return
 
    subscription = (
        db.query(UserStrategy)
        .filter(UserStrategy.id == target.user_strategy_id)
        .first()
    )
    if subscription is None:
        return
 
    if target.action == "buy":
        if subscription.allocated_amount is None and execution.order_amount:
            subscription.allocated_amount = float(execution.order_amount)
        return
 
    if target.action == "sell":
        volume = execution.executed_volume or 0
        price = execution.average_price or target.price
        proceeds = float(volume) * float(price)
        if proceeds > 0:
            subscription.allocated_amount = proceeds
 
 
def _place_live_order(
    db: Session,
    target: ExecutionTarget,
    preflight: PreflightResult,
    execution: StrategyExecution,
) -> None:
    """검사를 통과한 신호를 Upbit에 제출하고 주문 및 거래 결과를 저장합니다."""
    api_key = db.query(ApiKey).filter(ApiKey.user_id == target.user_id).first()
    try:
        access_key, secret_key = resolve_exchange_credentials(api_key)
        order = _execute_order(target, preflight, access_key, secret_key)
    except ValueError as error:
        execution.status = "failed"
        execution.error_message = str(error)
    else:
        _apply_order_result(execution, order)
        db.add(_trade_from_order(target, execution, order))
        _sync_allocated_amount(db, target, execution)
    db.commit()
 
 
def _place_paper_order(
    db: Session,
    target: ExecutionTarget,
    execution: StrategyExecution,
) -> None:
    """모의계좌 현금과 전략별 가상 포지션을 사용해 신호 가격으로 체결합니다."""
    execute_paper_order(db, execution, target.invest_ratio)
    db.commit()
 
 
def _execute_order(
    target: ExecutionTarget,
    preflight: PreflightResult,
    access_key: str,
    secret_key: str,
) -> LiveOrderResult:
    """신호 방향에 맞는 시장가 주문 함수를 선택합니다."""
    if target.action == "buy":
        return execute_market_buy(
            access_key=access_key,
            secret_key=secret_key,
            market=target.market,
            amount=preflight.order_amount or 0,
        )
    return execute_market_sell(
        access_key=access_key,
        secret_key=secret_key,
        market=target.market,
        volume=preflight.order_volume or 0,
    )
 
 
def _apply_order_result(execution: StrategyExecution, order: LiveOrderResult) -> None:
    """정규화된 Upbit 결과를 사용자별 전략 실행 레코드에 반영합니다."""
    execution.status = order.status
    execution.order_uuid = order.order_uuid
    execution.executed_volume = order.executed_volume
    execution.average_price = order.average_price
    execution.error_message = order.error_message
 
 
def _trade_from_order(
    target: ExecutionTarget,
    execution: StrategyExecution,
    order: LiveOrderResult,
) -> Trade:
    """대시보드 거래 내역에 노출할 체결 레코드를 생성합니다."""
    return Trade(
        user_id=target.user_id,
        strategy_execution_id=execution.id,
        ticker=target.market,
        action=target.action,
        price=order.average_price or target.price,
        volume=order.executed_volume,
        status=order.status,
        raw_response=order.raw_response,
    )
 
 
def _notification_text(
    target: ExecutionTarget,
    preflight: PreflightResult | None,
    execution: StrategyExecution,
) -> str:
    """모의·검사·실주문 상태를 사용자 친화적인 Telegram 메시지로 변환합니다."""
    action_label = "매수" if target.action == "buy" else "매도"
    header = f"전략: {target.strategy_name}\n종목: {target.market}\n"
    exit_reason = {
        "stop_loss": "손절 조건 도달",
        "take_profit": "목표 수익률 도달",
        "manual": "사용자 수동 매도",
    }.get(target.signal_source)
    reason_line = f"매도 사유: {exit_reason}\n" if target.action == "sell" and exit_reason else ""
 
    if target.execution_mode == "simulated":
        if execution.status == "simulated_success":
            return (
                f"✅ [모의 체결] {action_label}\n\n{header}"
                f"💵 체결가: {execution.average_price or target.price:,.0f}원\n"
                f"💰 주문금액: {execution.order_amount or 0:,.0f}원\n"
                f"🪙 체결수량: {execution.executed_volume or 0:.8f}\n"
                f"{reason_line}"
                "\n📊 모의계좌 잔고와 포지션에 반영되었습니다."
            )
        return (
            f"❌ [모의 주문 실패] {action_label}\n\n{header}"
            f"⚠️ 사유: {execution.error_message or '모의 주문을 처리할 수 없습니다.'}"
        )
 
    if preflight and preflight.ready and not target.live_trading_enabled:
        return (
            f"🔎 [실전 준비 검사 완료] {action_label} 신호\n\n{header}"
            f"💰 예상 주문금액: {preflight.order_amount:,.0f}원\n"
            "ℹ️ API 키와 주문금액 검증만 완료했으며 실제 주문은 실행되지 않았습니다."
        )
 
    if execution.status in {"success", "submitted", "partially_filled"}:
        return (
            f"✅ [실전 주문 접수] {action_label}\n\n{header}"
            f"💰 주문금액: {execution.order_amount:,.0f}원\n"
            f"🪙 체결수량: {execution.executed_volume or 0:.8f}\n"
            f"{reason_line}"
            f"📌 상태: {execution.status}"
        )
 
    reason = execution.error_message or (preflight.reason if preflight else None)
    label = "실전 주문 실패" if execution.status == "failed" else "실전 준비 검사 실패"
    return (
        f"❌ [{label}] {action_label} 신호\n\n{header}"
        f"⚠️ 사유: {reason or '검사 결과를 확인할 수 없습니다.'}\n"
        "ℹ️ 실제 주문은 실행되지 않았습니다."
    )
 
 
def _notify(
    db: Session,
    target: ExecutionTarget,
    preflight: PreflightResult | None,
    execution: StrategyExecution,
) -> None:
    """Telegram 전송 성공 여부를 실행 레코드에 남깁니다."""
    if execution.status in {"simulated_skipped", "skipped"}:
        return
    if send_message(target.telegram_chat_id, _notification_text(target, preflight, execution)):
        execution.notification_sent = True
        db.commit()
 
 
def _create_execution_and_notify(target: ExecutionTarget) -> bool:
    """사용자 한 명의 신호를 원자적으로 기록한 뒤 필요 시 실제 주문과 알림을 처리합니다."""
    db = SessionLocal()
    try:
        # 서로 다른 신호가 동시에 도착해도 같은 사용자 전략의 주문 준비는 한 번씩
        # 처리합니다. 실행 레코드 commit 후에는 잠금이 즉시 해제됩니다.
        subscription = db.query(UserStrategy).filter(
            UserStrategy.id == target.user_strategy_id,
        ).with_for_update().one()
        # 일시정지는 설정과 기존 포지션을 유지하면서 신규 진입만 차단합니다.
        # 전략 매도 신호와 손절·익절은 계속 처리합니다.
        if target.action == "buy" and subscription.paused:
            return False
        if target.execution_mode == "simulated" and _has_pending_paper_action(db, target):
            return False
        preflight = (
            _prepare_live_execution(db, target)
            if target.execution_mode == "live"
            else None
        )
        execution = _create_execution(db, target, preflight)
        if execution is None:
            return False
 
        started = time.perf_counter()
        if target.execution_mode == "simulated":
            _place_paper_order(db, target, execution)
        elif preflight and preflight.ready and target.live_trading_enabled:
            _place_live_order(db, target, preflight, execution)
        ORDER_DURATION.labels(target.execution_mode, target.market, target.action).observe(
            time.perf_counter() - started
        )
        STRATEGY_EXECUTIONS.labels(
            target.execution_mode, target.market, target.action, execution.status
        ).inc()
        if target.execution_mode == "simulated" or target.live_trading_enabled:
            ORDERS.labels(
                target.execution_mode, target.market, target.action, execution.status
            ).inc()
 
        _notify(db, target, preflight, execution)
        return True
    finally:
        db.close()
 
 
async def dispatch_signal(
    signal_id: int,
    user_id: int | None = None,
    mode: str | None = None,
) -> int:
    """활성 사용자를 병렬 처리하고 새로 생성된 실행 레코드 수를 반환합니다."""
    targets = await asyncio.to_thread(_targets_for_signal, signal_id, user_id, mode)
    if not targets:
        return 0

    results = await asyncio.gather(
        *(asyncio.to_thread(_create_execution_and_notify, target) for target in targets)
    )
    return sum(1 for created in results if created)

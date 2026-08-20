"""전략 주문과 귀속 조정 원장을 투영해 논리적 전략 포지션을 계산합니다."""

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.position_sync import PositionSyncAdjustment
from app.models.strategy import Strategy, UserStrategy
from app.models.strategy_signal import StrategyExecution, StrategySignal


@dataclass(frozen=True, slots=True)
class PositionEvent:
    kind: str
    volume: float
    price: float | None
    occurred_at: datetime
    source_id: int
    paid_fee: float | None = None


@dataclass(frozen=True, slots=True)
class CalculatedPosition:
    volume: float
    cost_basis: float
    average_buy_price: float | None


@dataclass(frozen=True, slots=True)
class StrategyPerformance:
    position: CalculatedPosition
    realized_profit_loss: float
    sold_cost_basis: float


def project_position(events: Iterable[PositionEvent]) -> CalculatedPosition:
    """시간순 원장으로 수량과 평균원가를 계산합니다.

    sell/deduct는 현재 평균원가로 원가를 비례 차감합니다. deduct는 실제
    매도가 아니므로 여기서는 실현손익을 만들지 않습니다.
    """
    volume = 0.0
    cost = 0.0
    for event in sorted(events, key=lambda item: (item.occurred_at, item.source_id, item.kind)):
        event_volume = max(0.0, float(event.volume))
        if event_volume <= 0:
            continue
        if event.kind == "execution_buy":
            price = float(event.price or 0)
            if price <= 0:
                continue
            volume += event_volume
            cost += event_volume * price
            continue
        if event.kind not in {"execution_sell", "deduct"} or volume <= 0:
            continue
        removed = min(event_volume, volume)
        average_price = cost / volume
        volume -= removed
        cost = max(0.0, cost - removed * average_price)

    if volume <= 1e-12:
        return CalculatedPosition(0.0, 0.0, None)
    return CalculatedPosition(volume, cost, cost / volume)


def project_strategy_performance(
    events: Iterable[PositionEvent],
    fee_rate: float = 0.0005,
) -> StrategyPerformance:
    """귀속 원가를 포함하되 실제 execution 매도에서만 손익을 확정합니다."""
    volume = 0.0
    cost = 0.0
    realized = 0.0
    sold_cost_basis = 0.0
    for event in sorted(events, key=lambda item: (item.occurred_at, item.source_id, item.kind)):
        event_volume = max(0.0, float(event.volume))
        if event_volume <= 0:
            continue
        if event.kind == "execution_buy":
            price = float(event.price or 0)
            if price <= 0:
                continue
            buy_fee = (
                float(event.paid_fee)
                if event.paid_fee is not None
                else event_volume * price * fee_rate
            )
            volume += event_volume
            cost += event_volume * price + buy_fee
            continue
        if event.kind not in {"execution_sell", "deduct"} or volume <= 0:
            continue
        removed = min(event_volume, volume)
        average_cost = cost / volume
        removed_cost = removed * average_cost
        if event.kind == "execution_sell":
            sell_fee = (
                float(event.paid_fee) * (removed / event_volume)
                if event.paid_fee is not None
                else removed * float(event.price or 0) * fee_rate
            )
            proceeds = removed * float(event.price or 0) - sell_fee
            realized += proceeds - removed_cost
            sold_cost_basis += removed_cost
        volume -= removed
        cost = max(0.0, cost - removed_cost)
    position = (
        CalculatedPosition(0.0, 0.0, None)
        if volume <= 1e-12
        else CalculatedPosition(volume, cost, cost / volume)
    )
    return StrategyPerformance(position, realized, sold_cost_basis)


def _execution_events(
    executions: Iterable[StrategyExecution],
    success_statuses: frozenset[str],
) -> list[PositionEvent]:
    events = []
    for execution in executions:
        if execution.status not in success_statuses or not execution.executed_volume:
            continue
        if execution.action not in {"buy", "sell"}:
            continue
        events.append(PositionEvent(
            kind=f"execution_{execution.action}",
            volume=float(execution.executed_volume),
            price=float(execution.average_price or execution.price),
            occurred_at=execution.created_at,
            source_id=execution.id,
            paid_fee=getattr(execution, "paid_fee", None),
        ))
    return events


def _adjustment_events(
    adjustments: Iterable[PositionSyncAdjustment],
) -> list[PositionEvent]:
    events = []
    for adjustment in adjustments:
        # 신규 정책에서는 감소 조정만 전략 포지션에 반영합니다. 과거 assign/buy
        # 행은 감사 원장으로 보존하되 외부 자산을 전략 소유로 만들지 않습니다.
        action = "deduct" if adjustment.action in {"deduct", "sell"} else None
        if action is None:
            continue
        events.append(PositionEvent(
            kind=action,
            volume=float(adjustment.volume),
            price=None,
            occurred_at=adjustment.created_at,
            # 서로 다른 테이블의 PK가 같아도 정렬이 안정적이도록 별도 공간을 둡니다.
            source_id=1_000_000_000 + adjustment.id,
        ))
    return events


def position_events_from_ledgers(
    execution_rows: Iterable[tuple[StrategyExecution, str]],
    adjustments: Iterable[PositionSyncAdjustment],
    success_statuses: frozenset[str],
) -> list[PositionEvent]:
    """legacy external_sync와 positive attribution을 포지션에서 제외합니다."""
    executions = [
        execution for execution, signal_source in execution_rows
        if signal_source != "external_sync"
    ]
    return _execution_events(executions, success_statuses) + _adjustment_events(adjustments)


def calculate_position(
    executions: list[StrategyExecution],
    success_statuses: frozenset[str] = frozenset({"success"}),
) -> CalculatedPosition:
    """기존 호출부와 모의투자를 위한 순수 execution 포지션 계산기입니다."""
    return project_position(_execution_events(executions, success_statuses))


def load_strategy_events(
    db: Session,
    user_strategy_id: int,
    mode: str,
) -> list[PositionEvent]:
    """실제 주문과 독립 조정을 중복 없이 공통 포지션 이벤트로 읽습니다."""
    subscription = (
        db.query(UserStrategy, Strategy.code)
        .join(Strategy, Strategy.id == UserStrategy.strategy_id)
        .filter(UserStrategy.id == user_strategy_id)
        .first()
    )
    if subscription is None or subscription[1] == "manual_hold_v1":
        return []

    success_statuses = (
        frozenset({"simulated_success"})
        if mode == "simulated"
        else frozenset({"success", "partially_filled"})
    )
    execution_rows = (
        db.query(StrategyExecution, StrategySignal.source)
        .join(StrategySignal, StrategySignal.id == StrategyExecution.signal_id)
        .filter(
            StrategyExecution.user_strategy_id == user_strategy_id,
            StrategyExecution.mode == mode,
            StrategyExecution.status.in_(success_statuses),
        )
        .order_by(StrategyExecution.created_at, StrategyExecution.id)
        .all()
    )
    # legacy external_sync와 assign adjustment는 감사 기록으로만 보존합니다.
    adjustments = []
    if mode == "live":
        adjustments = (
            db.query(PositionSyncAdjustment)
            .filter(PositionSyncAdjustment.user_strategy_id == user_strategy_id)
            .order_by(PositionSyncAdjustment.created_at, PositionSyncAdjustment.id)
            .all()
        )
    return position_events_from_ledgers(execution_rows, adjustments, success_statuses)


def load_strategy_position(
    db: Session,
    user_strategy_id: int,
    mode: str,
) -> CalculatedPosition:
    """한 전략의 논리적 포지션을 읽는 단일 DB 진입점입니다."""
    return project_position(load_strategy_events(db, user_strategy_id, mode))


def load_execution_position(
    db: Session,
    user_strategy_id: int,
    mode: str,
) -> CalculatedPosition:
    """실제 전략 주문만으로 남아 있는 포지션을 계산합니다.

    예산 예약에서는 실제 BUY/SELL에서 남은 수량만 확인할 때 사용합니다.
    """
    success_statuses = (
        frozenset({"simulated_success"})
        if mode == "simulated"
        else frozenset({"success", "partially_filled"})
    )
    rows = (
        db.query(StrategyExecution, StrategySignal.source)
        .join(StrategySignal, StrategySignal.id == StrategyExecution.signal_id)
        .filter(
            StrategyExecution.user_strategy_id == user_strategy_id,
            StrategyExecution.mode == mode,
            StrategyExecution.status.in_(success_statuses),
        )
        .order_by(StrategyExecution.created_at, StrategyExecution.id)
        .all()
    )
    executions = [
        execution for execution, signal_source in rows
        if signal_source != "external_sync"
    ]
    return calculate_position(executions, success_statuses)


def load_strategy_performance(
    db: Session,
    user_strategy_id: int,
    mode: str,
) -> StrategyPerformance:
    return project_strategy_performance(load_strategy_events(db, user_strategy_id, mode))

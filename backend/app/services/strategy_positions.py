"""전략 주문과 귀속 조정 원장을 투영해 논리적 전략 포지션을 계산합니다."""

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.position_sync import PositionSyncAdjustment
from app.models.strategy import Strategy, UserStrategy
from app.models.strategy_signal import StrategyExecution, StrategySignal

DEFAULT_FEE_RATE = 0.0005


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


@dataclass(frozen=True, slots=True)
class ProjectedEvent:
    entry_price: float | None
    transaction_amount: float
    fee: float
    realized_profit_loss: float | None


@dataclass(frozen=True, slots=True)
class LedgerProjection:
    position: CalculatedPosition
    realized_profit_loss: float
    sold_cost_basis: float
    events: dict[int, ProjectedEvent]


@dataclass(frozen=True, slots=True)
class ExecutionTradeDetail:
    entry_price: float | None
    transaction_amount: float | None
    realized_profit_loss: float | None


def project_ledger(
    events: Iterable[PositionEvent],
    *,
    include_buy_fees_in_cost: bool,
    fee_rate: float = DEFAULT_FEE_RATE,
) -> LedgerProjection:
    """평균원가 방식으로 포지션과 체결별 손익을 한 번에 투영합니다."""
    volume = 0.0
    cost = 0.0
    gross_cost = 0.0
    realized = 0.0
    sold_cost_basis = 0.0
    projected_events: dict[int, ProjectedEvent] = {}
    for event in sorted(events, key=lambda item: (item.occurred_at, item.source_id, item.kind)):
        event_volume = max(0.0, float(event.volume))
        if event_volume <= 0:
            continue
        price = float(event.price or 0)
        transaction_amount = event_volume * price
        execution_fee = 0.0
        if event.kind in {"execution_buy", "execution_sell"}:
            execution_fee = (
                float(event.paid_fee)
                if event.paid_fee is not None
                else transaction_amount * fee_rate
            )
        if event.kind == "execution_buy":
            if price <= 0:
                continue
            volume += event_volume
            gross_cost += transaction_amount
            cost += transaction_amount + (execution_fee if include_buy_fees_in_cost else 0.0)
            projected_events[event.source_id] = ProjectedEvent(
                entry_price=price,
                transaction_amount=transaction_amount,
                fee=execution_fee,
                realized_profit_loss=None,
            )
            continue
        if event.kind not in {"execution_sell", "deduct"} or volume <= 0:
            if event.kind == "execution_sell":
                projected_events[event.source_id] = ProjectedEvent(
                    entry_price=None,
                    transaction_amount=transaction_amount,
                    fee=execution_fee,
                    realized_profit_loss=None,
                )
            continue
        removed = min(event_volume, volume)
        average_cost = cost / volume
        average_entry_price = gross_cost / volume
        removed_cost = removed * average_cost
        removed_gross_cost = removed * average_entry_price
        event_realized = None
        if event.kind == "execution_sell":
            matched_sell_fee = execution_fee * (removed / event_volume)
            event_realized = removed * price - matched_sell_fee - removed_cost
            realized += event_realized
            sold_cost_basis += removed_cost
            projected_events[event.source_id] = ProjectedEvent(
                entry_price=average_entry_price,
                transaction_amount=transaction_amount,
                fee=execution_fee,
                realized_profit_loss=event_realized,
            )
        volume -= removed
        cost = max(0.0, cost - removed_cost)
        gross_cost = max(0.0, gross_cost - removed_gross_cost)

    position = (
        CalculatedPosition(0.0, 0.0, None)
        if volume <= 1e-12
        else CalculatedPosition(volume, cost, cost / volume)
    )
    return LedgerProjection(position, realized, sold_cost_basis, projected_events)


def project_position(events: Iterable[PositionEvent]) -> CalculatedPosition:
    """시간순 원장에서 운영 포지션의 수량과 평균 체결원가를 계산합니다."""
    return project_ledger(events, include_buy_fees_in_cost=False).position


def project_strategy_performance(
    events: Iterable[PositionEvent],
    fee_rate: float = DEFAULT_FEE_RATE,
) -> StrategyPerformance:
    """귀속 원가를 포함하되 실제 execution 매도에서만 손익을 확정합니다."""
    projection = project_ledger(
        events,
        include_buy_fees_in_cost=True,
        fee_rate=fee_rate,
    )
    return StrategyPerformance(
        projection.position,
        projection.realized_profit_loss,
        projection.sold_cost_basis,
    )


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


def execution_trade_details(
    executions: list[StrategyExecution],
    adjustments: list[PositionSyncAdjustment] | None = None,
    fee_rate: float = DEFAULT_FEE_RATE,
) -> dict[int, ExecutionTradeDetail]:
    """공통 평균원가 투영기로 체결 내역 화면의 상세 값을 계산합니다."""
    grouped_events: dict[int, list[PositionEvent]] = {}
    result: dict[int, ExecutionTradeDetail] = {}
    for execution in executions:
        success_statuses = (
            frozenset({"simulated_success"})
            if execution.mode == "simulated"
            else frozenset({"success", "partially_filled"})
        )
        events = _execution_events([execution], success_statuses)
        if not events:
            result[execution.id] = ExecutionTradeDetail(None, None, None)
            continue
        grouped_events.setdefault(execution.user_strategy_id, []).extend(events)

    for adjustment in adjustments or []:
        grouped_events.setdefault(adjustment.user_strategy_id, []).extend(
            _adjustment_events([adjustment])
        )

    for events in grouped_events.values():
        projection = project_ledger(
            events,
            include_buy_fees_in_cost=True,
            fee_rate=fee_rate,
        )
        for event in events:
            detail = projection.events.get(event.source_id)
            if detail is None:
                result[event.source_id] = ExecutionTradeDetail(
                    entry_price=None,
                    transaction_amount=event.volume * float(event.price or 0),
                    realized_profit_loss=None,
                )
                continue
            result[event.source_id] = ExecutionTradeDetail(
                entry_price=detail.entry_price,
                transaction_amount=detail.transaction_amount,
                realized_profit_loss=detail.realized_profit_loss,
            )
    return result


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


def load_strategy_performance(
    db: Session,
    user_strategy_id: int,
    mode: str,
) -> StrategyPerformance:
    return project_strategy_performance(load_strategy_events(db, user_strategy_id, mode))

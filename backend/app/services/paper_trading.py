"""모의계좌 입출금, 체결, 평가금액 계산을 담당합니다."""
 
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
 
from sqlalchemy.orm import Session
 
from app.models.paper_account import PaperAccount, PaperLedger
from app.models.strategy import SupportedMarket, UserStrategy
from app.models.strategy_signal import StrategyExecution, StrategyRuntime
from app.models.user import User
from app.services.execution_preflight import MIN_KRW_ORDER
from app.services.strategy_allocation import budget_for_buy
from app.services.strategy_positions import calculate_position
 
PAPER_FEE_RATE = Decimal("0.0005")
KRW_UNIT = Decimal("1")
MONEY_UNIT = Decimal("0.01")
 
 
@dataclass(frozen=True, slots=True)
class PaperAccountValue:
    cash_balance: Decimal
    net_deposit: Decimal
    holdings_value: Decimal
    total_equity: Decimal
    profit_loss: Decimal
 
 
def _paper_executions(db: Session, user_strategy_id: int) -> list[StrategyExecution]:
    return (
        db.query(StrategyExecution)
        .filter(
            StrategyExecution.user_strategy_id == user_strategy_id,
            StrategyExecution.status == "simulated_success",
        )
        .order_by(StrategyExecution.created_at, StrategyExecution.id)
        .all()
    )
 
 
def get_or_create_paper_account(db: Session, user_id: int, lock: bool = False) -> PaperAccount:
    query = db.query(PaperAccount).filter(PaperAccount.user_id == user_id)
    account = query.with_for_update().first() if lock else query.first()
    if account is not None:
        return account
 
    # 사용자 행을 잠가 동시에 최초 계좌를 만드는 경우도 직렬화합니다.
    db.query(User).filter(User.id == user_id).with_for_update().one()
    account = PaperAccount(user_id=user_id, cash_balance=0, net_deposit=0)
    db.add(account)
    db.flush()
    return account
 
 
def adjust_net_deposit(db: Session, user_id: int, target: Decimal) -> PaperAccount:
    """목표 순입금액과 현재 값의 차이를 입금 또는 가용 현금 출금으로 반영합니다."""
    if target < 0:
        raise ValueError("모의 투자금은 0원 이상이어야 합니다.")
    account = get_or_create_paper_account(db, user_id, lock=True)
    current = Decimal(account.net_deposit)
    difference = (target - current).quantize(Decimal("0.01"))
    cash = Decimal(account.cash_balance)
    if difference < 0 and -difference > cash:
        raise ValueError("출금하려는 금액이 모의계좌의 가용 현금보다 큽니다.")
    if difference == 0:
        return account
 
    account.net_deposit = target
    account.cash_balance = cash + difference
    db.add(
        PaperLedger(
            account_id=account.id,
            kind="deposit" if difference > 0 else "withdraw",
            amount=difference,
            balance_after=account.cash_balance,
        )
    )
    db.commit()
    db.refresh(account)
    return account
 
 
def apply_cash_adjustment(
    db: Session,
    user_id: int,
    amount: Decimal,
    action: str,
) -> PaperAccount:
    """입력한 금액만큼 모의계좌에 입금하거나 가용 현금에서 출금합니다."""
    if amount <= 0:
        raise ValueError("입출금 금액은 0원보다 커야 합니다.")
    if action not in {"deposit", "withdraw"}:
        raise ValueError("지원하지 않는 입출금 구분입니다.")
 
    account = get_or_create_paper_account(db, user_id, lock=True)
    cash = Decimal(account.cash_balance)
    net_deposit = Decimal(account.net_deposit)
    signed_amount = amount if action == "deposit" else -amount
 
    if action == "withdraw":
        if amount > cash:
            raise ValueError("출금하려는 금액이 모의계좌의 가용 현금보다 큽니다.")
        if amount > net_deposit:
            raise ValueError("출금하려는 금액이 현재 순입금액보다 큽니다.")
 
    account.cash_balance = cash + signed_amount
    account.net_deposit = net_deposit + signed_amount
    db.add(
        PaperLedger(
            account_id=account.id,
            kind=action,
            amount=signed_amount,
            balance_after=account.cash_balance,
        )
    )
    db.commit()
    db.refresh(account)
    return account
 
 
def execute_paper_order(
    db: Session,
    execution: StrategyExecution,
    invest_ratio: float,
) -> None:
    """신호 가격을 체결가로 사용해 실제 주문과 유사한 모의 잔고 변화를 기록합니다."""
    account = get_or_create_paper_account(db, execution.user_id, lock=True)
    subscription = (
        db.query(UserStrategy)
        .filter(UserStrategy.id == execution.user_strategy_id)
        .first()
    )
    price = Decimal(str(execution.price))
    position = calculate_position(
        _paper_executions(db, execution.user_strategy_id),
        frozenset({"simulated_success"}),
    )
 
    if execution.action == "buy":
        if position.volume > 0:
            _skip(execution, "기존 모의 포지션을 보유 중이므로 중복 매수 신호를 건너뛰었습니다.")
            return
        cash = Decimal(account.cash_balance)
        allocated = subscription.allocated_amount if subscription else None
        amount = budget_for_buy(
            allocated_amount=allocated,
            available_cash=cash,
            invest_ratio=invest_ratio,
        )
        if amount * (Decimal("1") + PAPER_FEE_RATE) > cash:
            amount = (cash / (Decimal("1") + PAPER_FEE_RATE)).quantize(KRW_UNIT, rounding=ROUND_DOWN)
        if amount < MIN_KRW_ORDER:
            _fail(execution, f"모의 주문금액이 최소 주문금액 5,000원보다 작습니다 ({amount:,.0f}원).")
            return
 
        # 예산이 비어 있던 기존 구독이면 이번에 산정한 금액으로 확정합니다.
        if subscription is not None and subscription.allocated_amount is None:
            subscription.allocated_amount = float(amount)
 
        fee = (amount * PAPER_FEE_RATE).quantize(MONEY_UNIT)
        volume = amount / price
        total_cost = (amount + fee).quantize(MONEY_UNIT)
        account.cash_balance = (Decimal(account.cash_balance) - total_cost).quantize(MONEY_UNIT)
        execution.status = "simulated_success"
        execution.order_amount = float(amount)
        execution.executed_volume = float(volume)
        execution.average_price = float(price)
        _ledger(db, account, execution, "buy", -total_cost)
        return
 
    if execution.action == "sell":
        if position.volume <= 0:
            _skip(execution, "보유 중인 모의 포지션이 없어 매도 신호를 건너뛰었습니다.")
            return
        volume = Decimal(str(position.volume))
        gross = volume * price
        fee = (gross * PAPER_FEE_RATE).quantize(MONEY_UNIT)
        proceeds = (gross - fee).quantize(MONEY_UNIT)
        account.cash_balance = (Decimal(account.cash_balance) + proceeds).quantize(MONEY_UNIT)
        execution.status = "simulated_success"
        execution.order_amount = float(gross.quantize(KRW_UNIT, rounding=ROUND_DOWN))
        execution.order_volume = float(volume)
        execution.executed_volume = float(volume)
        execution.average_price = float(price)
 
        # 이번 매도로 회수한 현금을 다음 매수 예산으로 넘겨 손익을 반영합니다.
        if subscription is not None:
            subscription.allocated_amount = float(
                proceeds.quantize(KRW_UNIT, rounding=ROUND_DOWN)
            )
 
        _ledger(db, account, execution, "sell", proceeds)
        return
 
    _fail(execution, "지원하지 않는 모의 주문 방향입니다.")
 
 
def _fail(execution: StrategyExecution, reason: str) -> None:
    execution.status = "simulated_failed"
    execution.error_message = reason
 
 
def _skip(execution: StrategyExecution, reason: str) -> None:
    """정상적으로 무시한 신호를 주문 실패와 구분해 기록합니다."""
    execution.status = "simulated_skipped"
    execution.error_message = reason
 
 
def _ledger(
    db: Session,
    account: PaperAccount,
    execution: StrategyExecution,
    kind: str,
    amount: Decimal,
) -> None:
    db.add(
        PaperLedger(
            account_id=account.id,
            strategy_execution_id=execution.id,
            kind=kind,
            amount=amount,
            balance_after=account.cash_balance,
        )
    )
 
 
def account_value(db: Session, user_id: int) -> PaperAccountValue:
    """최신 전략 계산 가격으로 가상 보유분을 평가해 총자산과 손익을 계산합니다."""
    account = get_or_create_paper_account(db, user_id)
    subscriptions = db.query(UserStrategy).filter(
        UserStrategy.user_id == user_id,
        UserStrategy.mode == "simulated",
    ).all()
    holdings = Decimal("0")
    for subscription in subscriptions:
        position = calculate_position(
            _paper_executions(db, subscription.id),
            frozenset({"simulated_success"}),
        )
        if position.volume <= 0:
            continue
        market = db.query(SupportedMarket.code).filter(
            SupportedMarket.id == subscription.market_id
        ).scalar()
        runtime = (
            db.query(StrategyRuntime)
            .filter(
                StrategyRuntime.strategy_id == subscription.strategy_id,
                StrategyRuntime.market == market,
                StrategyRuntime.timeframe_minutes == subscription.timeframe_minutes,
            )
            .first()
        )
        mark_price = runtime.close_price if runtime else position.average_buy_price
        holdings += Decimal(str(position.volume)) * Decimal(str(mark_price or 0))
 
    cash = Decimal(account.cash_balance)
    net_deposit = Decimal(account.net_deposit)
    total = cash + holdings
    return PaperAccountValue(cash, net_deposit, holdings, total, total - net_deposit)
 
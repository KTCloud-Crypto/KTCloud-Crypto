from decimal import Decimal
 
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
 
from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.paper_account import PaperAccount, PaperLedger
from app.models.strategy import UserStrategy
from app.models.strategy_signal import StrategyExecution
from app.models.user import User
from app.schemas.paper import (
    PaperAccountAdjustmentIn,
    PaperAccountCashIn,
    PaperAccountOut,
    PaperLedgerOut,
)
from app.services.paper_trading import (
    account_value,
    adjust_net_deposit,
    apply_cash_adjustment,
    get_or_create_paper_account,
)
from app.services.execution_history import execution_trade_details
from app.services.strategy_allocation import available_for_order, reserved_amount
 
router = APIRouter(prefix="/paper-account", tags=["Paper Trading"])
 
 
def _account_out(db: Session, user_id: int) -> PaperAccountOut:
    value = account_value(db, user_id)
    return_rate = (
        float(value.profit_loss / value.net_deposit * 100)
        if value.net_deposit > 0
        else None
    )
    # 활성 전략이 확보했지만 아직 매수하지 않은 예산을 빼면 실제로 새 전략에
    # 배정할 수 있는 현금이 나옵니다.
    reserved = reserved_amount(db, user_id, "simulated")
    return PaperAccountOut(
        cash_balance=float(value.cash_balance),
        reserved_amount=float(reserved),
        available_for_order=float(
            available_for_order(value.cash_balance, reserved, reserve_fee=True)
        ),
        net_deposit=float(value.net_deposit),
        holdings_value=float(value.holdings_value),
        total_equity=float(value.total_equity),
        profit_loss=float(value.profit_loss),
        return_rate=return_rate,
    )
 
 
@router.get("", response_model=PaperAccountOut)
def read_paper_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaperAccountOut:
    get_or_create_paper_account(db, current_user.id)
    db.commit()
    return _account_out(db, current_user.id)
 
 
@router.put("", response_model=PaperAccountOut)
def update_paper_account(
    payload: PaperAccountAdjustmentIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaperAccountOut:
    try:
        adjust_net_deposit(db, current_user.id, Decimal(str(payload.target_net_deposit)))
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _account_out(db, current_user.id)
 
 
@router.post("/deposit", response_model=PaperAccountOut)
def deposit_paper_cash(
    payload: PaperAccountCashIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaperAccountOut:
    apply_cash_adjustment(
        db,
        current_user.id,
        Decimal(str(payload.amount)),
        "deposit",
    )
    return _account_out(db, current_user.id)
 
 
@router.post("/withdraw", response_model=PaperAccountOut)
def withdraw_paper_cash(
    payload: PaperAccountCashIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaperAccountOut:
    try:
        apply_cash_adjustment(
            db,
            current_user.id,
            Decimal(str(payload.amount)),
            "withdraw",
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _account_out(db, current_user.id)
 
 
@router.get("/ledger", response_model=list[PaperLedgerOut])
def list_paper_ledger(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PaperLedgerOut]:
    account = db.query(PaperAccount).filter(PaperAccount.user_id == current_user.id).first()
    if account is None:
        return []
    ledger_items = (
        db.query(PaperLedger)
        .filter(PaperLedger.account_id == account.id)
        .order_by(PaperLedger.created_at.desc())
        .limit(100)
        .all()
    )

    # 손익 계산에는 매수부터 이어진 평균원가 흐름이 필요해, 사용자의 모의 체결
    # 기록 전체를 가져와 계산합니다.
    executions = (
        db.query(StrategyExecution)
        .join(UserStrategy, UserStrategy.id == StrategyExecution.user_strategy_id)
        .filter(UserStrategy.user_id == current_user.id, StrategyExecution.mode == "simulated")
        .all()
    )
    trade_details = execution_trade_details(executions)

    return [
        PaperLedgerOut(
            id=item.id,
            kind=item.kind,
            amount=float(item.amount),
            balance_after=float(item.balance_after),
            created_at=item.created_at,
            realized_profit_loss=(
                trade_details[item.strategy_execution_id].realized_profit_loss
                if item.strategy_execution_id in trade_details else None
            ),
        )
        for item in ledger_items
    ]
 
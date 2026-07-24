from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.paper_account import PaperAccount, PaperLedger
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

router = APIRouter(prefix="/paper-account", tags=["Paper Trading"])


def _account_out(db: Session, user_id: int) -> PaperAccountOut:
    value = account_value(db, user_id)
    return_rate = (
        float(value.profit_loss / value.net_deposit * 100)
        if value.net_deposit > 0
        else None
    )
    return PaperAccountOut(
        cash_balance=float(value.cash_balance),
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
    return (
        db.query(PaperLedger)
        .filter(PaperLedger.account_id == account.id)
        .order_by(PaperLedger.created_at.desc())
        .limit(100)
        .all()
    )

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.api_key import ApiKey
from app.models.strategy_signal import StrategyExecution
from app.models.user import User
from app.schemas.positions import (
    LiveAccountSummaryOut,
    PositionReconciliationOut,
    PositionSyncIn,
    ReconciliationStrategyOut,
    UpbitBalanceOut,
)
from app.services.exchange_credentials import ExchangeCredentialsError, resolve_exchange_credentials
from app.services.upbit import UpbitApiKeyValidationError, get_accounts
from app.services.position_reconciliation import (
    recorded_strategy_positions,
    recorded_strategy_volumes,
    reconciliation_status,
)
from app.services.position_sync import PositionSyncError, apply_position_sync
from app.services.live_accounting import calculate_realized_profit
from app.services.upbit_service import get_current_price

router = APIRouter(
    prefix="/positions",
    tags=["Balances"],
)


def _load_accounts(db: Session, user_id: int) -> list[dict]:
    """사용자 키를 복호화해 Upbit 계좌 응답을 조회합니다."""
    api_key = db.query(ApiKey).filter(ApiKey.user_id == user_id).first()
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록된 Upbit API Key가 없습니다.")
    try:
        access_key, secret_key = resolve_exchange_credentials(api_key)
        return get_accounts(
            access_key=access_key,
            secret_key=secret_key,
            base_url=settings.upbit_api_base_url,
        )
    except (ExchangeCredentialsError, UpbitApiKeyValidationError) as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))


def _reconciliation_items(db: Session, user_id: int, accounts: list[dict]) -> list[PositionReconciliationOut]:
    """이미 조회한 계좌 응답과 전략 기록으로 API 응답을 조립합니다."""
    actual = {
        item["currency"]: (float(item["balance"]), float(item["locked"]))
        for item in accounts
        if item["currency"] != "KRW"
    }
    positions = recorded_strategy_positions(db, user_id)
    recorded = recorded_strategy_volumes(db, user_id)
    result = []
    for currency in sorted(set(actual) | set(recorded)):
        available, locked = actual.get(currency, (0.0, 0.0))
        total = available + locked
        strategy_volume = recorded.get(currency, 0.0)
        item_status, message = reconciliation_status(total, strategy_volume)
        result.append(PositionReconciliationOut(
            currency=currency,
            actual_available=available,
            actual_locked=locked,
            actual_total=total,
            strategy_volume=strategy_volume,
            difference=total - strategy_volume,
            status=item_status,
            message=message,
            strategies=[
                ReconciliationStrategyOut(
                    strategy_id=item.strategy.id,
                    subscription_id=item.subscription.id,
                    strategy_name=item.strategy.name,
                    market=item.market,
                    volume=item.volume,
                )
                for item in positions
                if item.market.endswith(f"-{currency}")
            ],
        ))
    return result


@router.get("/balance", response_model=list[UpbitBalanceOut])
def get_upbit_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UpbitBalanceOut]:
    """등록된 Upbit API Key로 실제 계좌 잔고를 실시간 조회합니다."""
    accounts = _load_accounts(db, current_user.id)

    return [
        UpbitBalanceOut(
            currency=account["currency"],
            balance=float(account["balance"]),
            locked=float(account["locked"]),
            avg_buy_price=float(account["avg_buy_price"]),
        )
        for account in accounts
    ]


@router.get("/summary", response_model=LiveAccountSummaryOut)
async def get_live_account_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LiveAccountSummaryOut:
    """확정 손익과 보유 코인의 평가손익을 합산해 실계좌 총 손익을 계산합니다."""
    accounts = [
        account
        for account in _load_accounts(db, current_user.id)
        if account["currency"] != "KRW"
        and float(account["balance"]) + float(account["locked"]) > 0
    ]
    prices = await asyncio.gather(*[
        get_current_price(f"KRW-{account['currency']}")
        for account in accounts
    ])

    purchase_amount = 0.0
    evaluation_amount = 0.0
    for account, current_price in zip(accounts, prices, strict=True):
        volume = float(account["balance"]) + float(account["locked"])
        purchase_amount += volume * float(account["avg_buy_price"])
        evaluation_amount += volume * current_price

    executions = (
        db.query(StrategyExecution)
        .filter(
            StrategyExecution.user_id == current_user.id,
            StrategyExecution.mode == "live",
            StrategyExecution.status == "success",
        )
        .order_by(StrategyExecution.created_at, StrategyExecution.id)
        .all()
    )
    realized = calculate_realized_profit(executions)
    unrealized_profit_loss = evaluation_amount - purchase_amount
    profit_loss = realized.profit_loss + unrealized_profit_loss
    profit_base = realized.sold_cost_basis + purchase_amount
    return LiveAccountSummaryOut(
        purchase_amount=purchase_amount,
        evaluation_amount=evaluation_amount,
        realized_profit_loss=realized.profit_loss,
        unrealized_profit_loss=unrealized_profit_loss,
        profit_loss=profit_loss,
        return_rate=(profit_loss / profit_base * 100) if profit_base > 0 else None,
    )


@router.get("/reconciliation", response_model=list[PositionReconciliationOut])
def reconcile_positions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PositionReconciliationOut]:
    """Upbit 실제 코인 보유량과 실전 전략의 미청산 기록을 비교합니다."""
    accounts = _load_accounts(db, current_user.id)
    return _reconciliation_items(db, current_user.id, accounts)


@router.post("/reconciliation/apply", status_code=204)
def apply_position_reconciliation(
    payload: PositionSyncIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """외부 매수·매도 차이를 사용자가 선택한 실전 전략 포지션에 반영합니다."""
    accounts = _load_accounts(db, current_user.id)
    try:
        apply_position_sync(
            db,
            user_id=current_user.id,
            accounts=accounts,
            subscription_id=payload.subscription_id,
            action=payload.action,
            volume=payload.volume,
            source="web",
        )
    except PositionSyncError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return Response(status_code=204)

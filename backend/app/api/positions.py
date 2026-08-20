import asyncio
import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.api_key import ApiKey
from app.models.position_sync import PositionSyncAdjustment
from app.models.strategy import Strategy, SupportedMarket, UserStrategy
from app.models.strategy_signal import StrategyRuntime
from app.models.user import User
from app.schemas.positions import (
    LiveAccountSummaryOut,
    PortfolioAllocationOut,
    PortfolioSummaryOut,
    PositionReconciliationOut,
    PositionDeductionBatchIn,
    ReconciliationStrategyOut,
    ExchangeAccountStatusOut,
    ExchangeAssetOut,
    PositionsDashboardOut,
    UpbitBalanceOut,
)
from app.services.exchange_credentials import ExchangeCredentialsError, resolve_exchange_credentials
from app.services.position_reconciliation import (
    actual_coin_totals,
    calculate_reconciliation_state,
    recorded_strategy_positions,
    recorded_strategy_volumes,
    reconciliation_status,
)
from app.services.position_deduction import PositionDeductionError, apply_position_deduction
from app.services.upbit import UpbitApiKeyValidationError, get_accounts
from app.services.strategy_positions import load_strategy_performance
from app.services.strategy_allocation import available_for_order, reserved_amount
from app.services.upbit_service import get_current_price
from app.services.signal_dispatcher import managed_live_positions_value
from app.services.audit import record_security_event

router = APIRouter(
    prefix="/positions",
    tags=["Balances"],
)


def _load_accounts(db: Session, user_id: int) -> list[dict]:
    """사용자 키를 복호화해 Upbit 계좌 응답을 조회합니다."""
    cache_key = f"upbit_accounts:{user_id}"
    cached = db.info.get(cache_key)
    if cached is not None:
        return cached
    api_key = db.query(ApiKey).filter(ApiKey.user_id == user_id).first()
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록된 Upbit API Key가 없습니다.")
    try:
        access_key, secret_key = resolve_exchange_credentials(api_key)
        accounts = get_accounts(
            access_key=access_key,
            secret_key=secret_key,
            base_url=settings.upbit_api_base_url,
        )
        db.info[cache_key] = accounts
        return accounts
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

        # 실제 보유량과 전략 기록 수량이 모두 0이면 제외
        if total == 0 and strategy_volume == 0:
            continue

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


@router.get("/portfolio", response_model=PortfolioSummaryOut)
def get_portfolio_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioSummaryOut:
    """실전투자 포트폴리오 배정 현황을 조회합니다."""
    accounts = _load_accounts(db, current_user.id)
    available_krw = sum(
        float(account["balance"])
        for account in accounts
        if account["currency"] == "KRW"
    )
    managed_positions_value = managed_live_positions_value(db, current_user.id)
    total_equity = available_krw + managed_positions_value

    # 활성 전략 목록
    strategies = (
        db.query(UserStrategy, Strategy, SupportedMarket)
        .join(Strategy, Strategy.id == UserStrategy.strategy_id)
        .join(SupportedMarket, SupportedMarket.id == UserStrategy.market_id)
        .filter(
            UserStrategy.user_id == current_user.id,
            UserStrategy.mode == "live",
            Strategy.code != "manual_hold_v1",
        )
        .all()
    )

    strategy_allocations = []
    positions = recorded_strategy_positions(db, current_user.id)
    for subscription, strategy, market in strategies:
        # 신규 구독과 금액 직접 설정은 저장 시점에 확정한 예산을 사용합니다.
        # allocated_amount가 없는 legacy 구독만 기존 비율 계산으로 보완합니다.
        allocation_amount = (
            subscription.allocated_amount
            if subscription.allocated_amount is not None
            else total_equity * subscription.invest_ratio
        )

        # 현재 포지션 평가액 계산
        current_position = next(
            (p for p in positions if p.subscription.id == subscription.id),
            None
        )
        current_position_value = 0.0
        if current_position and current_position.volume > 0:
            runtime = (
                db.query(StrategyRuntime)
                .filter(
                    StrategyRuntime.strategy_id == strategy.id,
                    StrategyRuntime.market == market.code,
                    StrategyRuntime.timeframe_minutes == subscription.timeframe_minutes,
                )
                .first()
            )
            mark_price = runtime.close_price if runtime else 0
            current_position_value = current_position.volume * mark_price

        strategy_allocations.append(PortfolioAllocationOut(
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            strategy_code=strategy.code,
            market=market.code,
            invest_ratio=subscription.invest_ratio,
            allocation_amount=allocation_amount,
            allocation_mode=subscription.allocation_mode,
            current_position_value=current_position_value,
            enabled=subscription.enabled,
        ))

    return PortfolioSummaryOut(
        available_krw=available_krw,
        managed_positions_value=managed_positions_value,
        total_equity=total_equity,
        strategies=strategy_allocations,
    )


async def _account_status(
    db: Session,
    user_id: int,
    accounts: list[dict],
) -> ExchangeAccountStatusOut:
    """한 번 조회한 Upbit 잔고로 계좌·전략·미배정 자산을 분리합니다."""
    positions = recorded_strategy_positions(db, user_id)
    recorded = recorded_strategy_volumes(db, user_id)
    supported = {
        item.code: item
        for item in db.query(SupportedMarket).filter(SupportedMarket.enabled.is_(True)).all()
    }
    coin_accounts = [
        item for item in accounts
        if item["currency"] != "KRW"
        and float(item["balance"]) + float(item["locked"]) > 0
    ]
    currencies = sorted({item["currency"] for item in coin_accounts} | set(recorded))
    price_results = await asyncio.gather(*[
        get_current_price(f"KRW-{currency}")
        for currency in currencies
    ], return_exceptions=True)
    prices = {
        currency: None if isinstance(price, Exception) else float(price)
        for currency, price in zip(currencies, price_results, strict=True)
    }
    krw = next((item for item in accounts if item["currency"] == "KRW"), None)
    available_krw = float(krw["balance"]) if krw else 0.0
    locked_krw = float(krw["locked"]) if krw else 0.0
    assets = []
    coin_evaluation = 0.0
    managed_value = 0.0
    unallocated_value = 0.0
    by_currency = {item["currency"]: item for item in coin_accounts}
    for currency in currencies:
        account = by_currency.get(currency)
        available = float(account["balance"]) if account else 0.0
        locked = float(account["locked"]) if account else 0.0
        total = available + locked
        strategy_volume = recorded.get(currency, 0.0)
        state = calculate_reconciliation_state(total, strategy_volume)
        item_status = state.status
        unallocated = state.unallocated_volume
        shortfall = state.shortfall_volume
        price = prices.get(currency)
        evaluation = total * price if price is not None else None
        unallocated_evaluation = unallocated * price if price is not None else None
        if evaluation is not None:
            coin_evaluation += evaluation
            managed_value += strategy_volume * price
        if unallocated_evaluation is not None:
            unallocated_value += unallocated_evaluation
        market_code = f"KRW-{currency}"
        assets.append(ExchangeAssetOut(
            currency=currency,
            market=market_code if market_code in supported else None,
            supported=market_code in supported,
            available=available,
            locked=locked,
            total=total,
            average_buy_price=float(account["avg_buy_price"]) if account else 0.0,
            current_price=price,
            evaluation_amount=evaluation,
            strategy_volume=strategy_volume,
            unallocated_volume=unallocated,
            unallocated_value=unallocated_evaluation,
            shortfall_volume=shortfall,
            reconciliation_status=item_status,
            strategies=[
                ReconciliationStrategyOut(
                    strategy_id=item.strategy.id,
                    subscription_id=item.subscription.id,
                    strategy_name=item.strategy.name,
                    market=item.market,
                    volume=item.volume,
                )
                for item in positions if item.market == market_code
            ],
        ))
    total_krw = available_krw + locked_krw
    strategy_reserved_krw = float(reserved_amount(db, user_id, "live"))
    strategy_available_krw = float(available_for_order(available_krw, strategy_reserved_krw))
    return ExchangeAccountStatusOut(
        available_krw=available_krw,
        strategy_reserved_krw=strategy_reserved_krw,
        strategy_available_krw=strategy_available_krw,
        locked_krw=locked_krw,
        total_krw=total_krw,
        coin_evaluation_amount=coin_evaluation,
        account_equity=total_krw + coin_evaluation,
        managed_positions_value=managed_value,
        managed_equity=available_krw + managed_value,
        unallocated_value=unallocated_value,
        assets=assets,
    )


@router.get("/dashboard", response_model=PositionsDashboardOut)
async def get_positions_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PositionsDashboardOut:
    """한 번의 거래소 잔고 조회로 실전투자 화면 전체 상태를 조립합니다."""
    accounts = _load_accounts(db, current_user.id)
    balances = [
        UpbitBalanceOut(
            currency=item["currency"],
            balance=float(item["balance"]),
            locked=float(item["locked"]),
            avg_buy_price=float(item["avg_buy_price"]),
        )
        for item in accounts
        if float(item["balance"]) + float(item["locked"]) > 0
    ]
    # 기존 응답 계약은 유지하면서 신규 화면은 명확한 account 필드를 사용합니다.
    portfolio = get_portfolio_summary(db=db, current_user=current_user)
    return PositionsDashboardOut(
        balances=balances,
        reconciliation=_reconciliation_items(db, current_user.id, accounts),
        portfolio=portfolio,
        account=await _account_status(db, current_user.id, accounts),
    )


@router.get("/balance", response_model=list[UpbitBalanceOut])
def get_upbit_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UpbitBalanceOut]:
    """등록된 Upbit API Key로 실제 계좌 잔고를 실시간 조회합니다. 보유량이 0인 종목은 제외합니다."""
    accounts = _load_accounts(db, current_user.id)

    return [
        UpbitBalanceOut(
            currency=account["currency"],
            balance=float(account["balance"]),
            locked=float(account["locked"]),
            avg_buy_price=float(account["avg_buy_price"]),
        )
        for account in accounts
        if float(account["balance"]) + float(account["locked"]) > 0
    ]


@router.get("/summary", response_model=LiveAccountSummaryOut)
async def get_live_account_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LiveAccountSummaryOut:
    """외부 미배정 자산을 제외한 전략 귀속 자산의 추정 성과입니다."""
    subscriptions = (
        db.query(UserStrategy, Strategy, SupportedMarket)
        .join(Strategy, Strategy.id == UserStrategy.strategy_id)
        .join(SupportedMarket, SupportedMarket.id == UserStrategy.market_id)
        .filter(
            UserStrategy.user_id == current_user.id,
            UserStrategy.mode == "live",
            Strategy.code != "manual_hold_v1",
        )
        .all()
    )
    projected = [
        (load_strategy_performance(db, subscription.id, "live"), market.code)
        for subscription, _, market in subscriptions
    ]
    prices = await asyncio.gather(*[
        get_current_price(market) for performance, market in projected
        if performance.position.volume > 0
    ], return_exceptions=True)
    purchase_amount = 0.0
    evaluation_amount = 0.0
    open_positions = [item for item in projected if item[0].position.volume > 0]
    for (performance, _), current_price in zip(open_positions, prices, strict=True):
        if isinstance(current_price, Exception):
            continue
        purchase_amount += performance.position.cost_basis
        evaluation_amount += performance.position.volume * current_price

    realized_profit_loss = sum(item[0].realized_profit_loss for item in projected)
    sold_cost_basis = sum(item[0].sold_cost_basis for item in projected)
    unrealized_profit_loss = evaluation_amount - purchase_amount
    profit_loss = realized_profit_loss + unrealized_profit_loss
    profit_base = sold_cost_basis + purchase_amount
    return LiveAccountSummaryOut(
        purchase_amount=purchase_amount,
        evaluation_amount=evaluation_amount,
        realized_profit_loss=realized_profit_loss,
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


@router.post("/reconciliation/deduct", status_code=204)
def apply_position_deductions(
    payload: PositionDeductionBatchIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """한 종목의 shortfall을 여러 전략에서 하나의 트랜잭션으로 차감합니다."""
    currency = payload.currency.upper()
    if len({item.subscription_id for item in payload.deductions}) != len(payload.deductions):
        raise HTTPException(status_code=409, detail="동일한 전략을 중복 선택할 수 없습니다.")
    request_keys = [
        hashlib.sha256(f"{payload.idempotency_key}:{index}".encode()).hexdigest()
        for index in range(len(payload.deductions))
    ] if payload.idempotency_key else []
    if request_keys:
        existing_count = db.query(PositionSyncAdjustment.id).filter(
            PositionSyncAdjustment.idempotency_key.in_(request_keys),
        ).count()
        if existing_count == len(request_keys):
            return Response(status_code=204)
        if existing_count:
            raise HTTPException(status_code=409, detail="일부 차감만 기록된 요청입니다. 관리자 확인이 필요합니다.")
    db.query(User).filter(User.id == current_user.id).with_for_update().one()
    accounts = _load_accounts(db, current_user.id)
    actual = actual_coin_totals(accounts).get(currency, 0.0)
    strategy_total = recorded_strategy_volumes(db, current_user.id).get(currency, 0.0)
    difference = actual - strategy_total
    tolerance = max(1e-8, strategy_total * 1e-4)
    if difference >= -tolerance:
        raise HTTPException(status_code=409, detail="현재 차감할 실제 잔고 부족분이 없습니다.")
    if abs(payload.expected_difference - difference) > tolerance:
        raise HTTPException(status_code=409, detail="잔고 상태가 변경되었습니다. 새로고침 후 다시 시도해 주세요.")
    requested = sum(item.volume for item in payload.deductions)
    if requested > -difference + tolerance:
        raise HTTPException(status_code=409, detail="전체 차감 수량이 현재 부족 수량보다 큽니다.")
    position_by_subscription = {
        item.subscription.id: item
        for item in recorded_strategy_positions(db, current_user.id)
    }
    for deduction in payload.deductions:
        selected = position_by_subscription.get(deduction.subscription_id)
        if selected is None or not selected.market.endswith(f"-{currency}"):
            raise HTTPException(status_code=409, detail="선택한 종목의 실전 전략이 아닙니다.")
        if deduction.volume > selected.volume + tolerance:
            raise HTTPException(status_code=409, detail="전략 보유 수량보다 많이 차감할 수 없습니다.")
    try:
        for index, deduction in enumerate(payload.deductions):
            apply_position_deduction(
                db,
                user_id=current_user.id,
                accounts=accounts,
                subscription_id=deduction.subscription_id,
                volume=deduction.volume,
                source="web",
                idempotency_key=(
                    request_keys[index] if request_keys else None
                ),
                commit=False,
            )
        db.commit()
    except PositionDeductionError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error
    record_security_event(
        db, "position_reconciled", "success", actor_user_id=current_user.id,
        resource_type="currency", resource_id=currency, request=request,
        metadata={"action": "deduct", "count": len(payload.deductions), "source": "web"},
    )
    return Response(status_code=204)

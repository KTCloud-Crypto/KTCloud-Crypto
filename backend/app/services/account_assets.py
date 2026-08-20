"""Upbit 계좌 잔고를 전략 관리 자산과 외부 미배정 자산으로 분류합니다."""

from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session

from app.models.strategy import SupportedMarket
from app.schemas.positions import (
    ExchangeAccountStatusOut,
    ExchangeAssetOut,
    ReconciliationStrategyOut,
)
from app.services.position_reconciliation import (
    calculate_reconciliation_state,
    recorded_strategy_positions,
    recorded_strategy_volumes,
)
from app.services.strategy_allocation import available_for_order, reserved_amount
from app.services.upbit_service import get_current_price


async def build_exchange_account_status(
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
        price = prices.get(currency)
        evaluation = total * price if price is not None else None
        unallocated_evaluation = (
            state.unallocated_volume * price
            if price is not None
            else None
        )
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
            unallocated_volume=state.unallocated_volume,
            unallocated_value=unallocated_evaluation,
            shortfall_volume=state.shortfall_volume,
            reconciliation_status=state.status,
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

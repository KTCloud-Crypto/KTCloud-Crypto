from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

import pyupbit

from app.models.api_key import ApiKey
from app.services.exchange_credentials import resolve_exchange_credentials
from app.services.strategy_allocation import portfolio_buy_amount

MIN_KRW_ORDER = Decimal("5000")
DEFAULT_BUY_FEE_RATE = Decimal("0.0005")
BUY_ORDER_RESERVE_KRW = Decimal("1")


@dataclass(frozen=True, slots=True)
class PreflightResult:
    ready: bool
    order_amount: float | None
    reason: str | None = None
    order_volume: float | None = None


def _available_balances(access_key: str, secret_key: str) -> dict[str, Decimal]:
    """Upbit 계좌 응답을 통화별 주문 가능 잔고로 정규화합니다."""
    try:
        response = pyupbit.Upbit(access_key, secret_key).get_balances()
    except Exception as error:
        raise ValueError("Upbit 계좌 조회에 실패했습니다. API 키와 허용 IP를 확인해 주세요.") from error

    if not isinstance(response, list):
        raise ValueError("Upbit 계좌 조회에 실패했습니다. API 권한과 허용 IP를 확인해 주세요.")

    balances: dict[str, Decimal] = {}
    for account in response:
        currency = account.get("currency")
        if currency:
            balances[currency] = Decimal(str(account.get("balance") or "0"))
    return balances


def _buy_fee_rate(access_key: str, secret_key: str, market: str) -> Decimal:
    """Upbit 주문 가능 정보에서 현재 종목의 매수 수수료율을 조회합니다."""
    try:
        response = pyupbit.Upbit(access_key, secret_key).get_chance(market)
        fee_rate = Decimal(str(response.get("bid_fee"))) if isinstance(response, dict) else None
        if fee_rate is not None and fee_rate >= 0:
            return fee_rate
    except Exception:
        pass
    return DEFAULT_BUY_FEE_RATE


def fee_adjusted_buying_power(
    available_krw: Decimal,
    fee_rate: Decimal,
) -> Decimal:
    """주문금액과 매수 수수료의 합이 가용 KRW를 넘지 않는 최대 정수 금액."""
    spendable = max(Decimal("0"), available_krw - BUY_ORDER_RESERVE_KRW)
    return (spendable / (Decimal("1") + max(Decimal("0"), fee_rate))).quantize(
        Decimal("1"),
        rounding=ROUND_DOWN,
    )


def validate_order_readiness(
    *,
    api_key: ApiKey | None,
    action: str,
    market: str,
    reference_price: float,
    invest_ratio: float,
    managed_positions_value: float = 0,
    current_position_value: float = 0,
) -> PreflightResult:
    """실제 주문 없이 API 키와 포트폴리오 배정 주문금액을 검사합니다."""
    try:
        access_key, secret_key = resolve_exchange_credentials(api_key)
        balances = _available_balances(access_key, secret_key)
    except ValueError as error:
        return PreflightResult(False, None, str(error))

    if action == "buy":
        available_krw = balances.get("KRW", Decimal("0"))
        portfolio_amount = portfolio_buy_amount(
            total_equity=available_krw + Decimal(str(managed_positions_value)),
            available_cash=available_krw,
            invest_ratio=invest_ratio,
            current_position_value=current_position_value,
        )
        fee_rate = _buy_fee_rate(access_key, secret_key, market)
        amount = min(
            portfolio_amount,
            fee_adjusted_buying_power(available_krw, fee_rate),
        )
    elif action == "sell":
        currency = market.split("-", maxsplit=1)[-1]
        amount = (balances.get(currency, Decimal("0")) * Decimal(str(reference_price))).quantize(
            Decimal("1"), rounding=ROUND_DOWN
        )
    else:
        return PreflightResult(False, None, "지원하지 않는 주문 방향입니다.")

    if amount < MIN_KRW_ORDER:
        return PreflightResult(
            False,
            float(amount),
            f"예상 주문금액이 Upbit 최소 주문금액 5,000원보다 작습니다 ({amount:,.0f}원).",
        )
    return PreflightResult(True, float(amount))


def validate_sell_readiness(
    *,
    api_key: ApiKey | None,
    market: str,
    reference_price: float,
    strategy_volume: float,
) -> PreflightResult:
    """전략이 보유한 수량만 대상으로 실제 매도 가능 여부를 검사합니다."""
    if strategy_volume <= 0:
        return PreflightResult(False, None, "이 전략으로 매수해 남아 있는 수량이 없습니다.")

    try:
        access_key, secret_key = resolve_exchange_credentials(api_key)
        balances = _available_balances(access_key, secret_key)
    except ValueError as error:
        return PreflightResult(False, None, str(error))

    currency = market.split("-", maxsplit=1)[-1]
    available_volume = balances.get(currency, Decimal("0"))
    requested_volume = Decimal(str(strategy_volume))
    if available_volume < requested_volume:
        return PreflightResult(
            False,
            None,
            "Upbit 가용 잔고가 이 전략의 기록된 매도 수량보다 부족합니다.",
            float(requested_volume),
        )

    amount = (requested_volume * Decimal(str(reference_price))).quantize(
        Decimal("1"), rounding=ROUND_DOWN
    )
    if amount < MIN_KRW_ORDER:
        return PreflightResult(
            False,
            float(amount),
            f"예상 주문금액이 Upbit 최소 주문금액 5,000원보다 작습니다 ({amount:,.0f}원).",
            float(requested_volume),
        )
    return PreflightResult(True, float(amount), order_volume=float(requested_volume))

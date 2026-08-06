from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
 
import pyupbit
 
from app.models.api_key import ApiKey
from app.services.exchange_credentials import resolve_exchange_credentials
from app.services.strategy_allocation import budget_for_buy
 
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
    """Upbit 계좌 응답을 통화별 주문 가능 잔고로 정규화합니다.

    잔고 조회는 시세와 무관해 재시도해도 안전하므로, 일시적인 네트워크
    지연이나 순간적인 응답 실패에 대비해 최대 2회까지 짧게 재시도합니다.
    코인 시세는 초 단위로도 크게 움직일 수 있어, 재시도 간격을 0.5초로
    타이트하게 잡아 전체 지연을 최소화합니다.
    """
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = pyupbit.Upbit(access_key, secret_key).get_balances()
            if not isinstance(response, list):
                raise ValueError("Upbit 계좌 조회에 실패했습니다. API 권한과 허용 IP를 확인해 주세요.")
            balances: dict[str, Decimal] = {}
            for account in response:
                currency = account.get("currency")
                if currency:
                    balances[currency] = Decimal(str(account.get("balance") or "0"))
            return balances
        except Exception as error:
            last_error = error
            if attempt < 2:
                time.sleep(0.5)
    raise ValueError("Upbit 계좌 조회에 실패했습니다. API 키와 허용 IP를 확인해 주세요.") from last_error
 
 
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
 
 
def available_krw_balance(api_key: ApiKey | None) -> Decimal:
    """구독 시점 예산 산정을 위해 현재 KRW 가용 잔고만 조회합니다."""
    access_key, secret_key = resolve_exchange_credentials(api_key)
    balances = _available_balances(access_key, secret_key)
    return balances.get("KRW", Decimal("0"))
 
 
def validate_order_readiness(
    *,
    api_key: ApiKey | None,
    action: str,
    market: str,
    reference_price: float,
    invest_ratio: float,
    allocated_amount: float | None = None,
) -> PreflightResult:
    """실제 주문 없이 API 키와 확정된 주문 예산을 검사합니다.
 
    매수 예산은 가용 KRW 현금만 기준으로 산정합니다. 보유 중인 포지션은
    이미 코인으로 바뀐 자산이므로 예산 계산에 포함하지 않습니다.
    """
    try:
        access_key, secret_key = resolve_exchange_credentials(api_key)
        balances = _available_balances(access_key, secret_key)
    except ValueError as error:
        return PreflightResult(False, None, str(error))
 
    if action == "buy":
        available_krw = balances.get("KRW", Decimal("0"))
        budget = budget_for_buy(
            allocated_amount=allocated_amount,
            available_cash=available_krw,
            invest_ratio=invest_ratio,
        )
        fee_rate = _buy_fee_rate(access_key, secret_key, market)
        amount = min(
            budget,
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
 
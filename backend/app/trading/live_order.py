from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

import pyupbit

ORDER_RETRY_COUNT = 1
ORDER_RETRY_DELAY_SECONDS = 1.0
DUPLICATE_CHECK_WINDOW_SECONDS = 10


@dataclass(frozen=True, slots=True)
class LiveOrderResult:
    success: bool
    status: str
    order_uuid: str | None = None
    executed_volume: float | None = None
    average_price: float | None = None
    paid_fee: float | None = None
    error_message: str | None = None
    raw_response: dict | None = None


def _error_message(response: object) -> str:
    """형태가 일정하지 않은 Upbit 오류 응답에서 사용자용 사유를 추출합니다."""
    if isinstance(response, dict):
        error = response.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error.get("name") or "Upbit 주문이 거절되었습니다.")
    return "Upbit 주문 응답을 확인할 수 없습니다."


def _parse_created_at(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _find_recent_matching_order(
    upbit: pyupbit.Upbit,
    market: str,
    side: str,
    within_seconds: float = DUPLICATE_CHECK_WINDOW_SECONDS,
) -> dict | None:
    """직전 요청이 응답을 못 받았을 뿐 실제로는 체결됐을 가능성을 확인합니다.

    재시도 전에 반드시 이 확인을 거쳐, 같은 주문이 두 번 나가는 것을
    방지합니다. 확인 자체가 실패하면(조회 오류 등) None을 반환해
    "모른다"로 처리하며, 이 경우 호출부에서 재시도 여부를 신중히 판단합니다.
    """
    try:
        orders = upbit.get_order(market, state="done")
    except Exception:
        return None
    if not isinstance(orders, list):
        return None

    now = datetime.now(timezone.utc)
    for order in orders:
        if not isinstance(order, dict) or order.get("side") != side:
            continue
        created_at = _parse_created_at(order.get("created_at"))
        if created_at is None:
            continue
        if (now - created_at).total_seconds() <= within_seconds:
            return order
    return None


def _submit_with_retry(
    *,
    upbit: pyupbit.Upbit,
    market: str,
    side: str,
    submit,
    failure_message: str,
) -> LiveOrderResult:
    """주문을 제출하고, 실패 시 중복 체결 여부를 확인한 뒤에만 안전하게 재시도합니다."""
    last_response: dict | None = None

    for attempt in range(ORDER_RETRY_COUNT + 1):
        try:
            response = submit()
        except Exception:
            response = None

        if isinstance(response, dict) and response.get("uuid"):
            return _resolve_order(upbit, response)

        if isinstance(response, dict):
            last_response = response

        is_last_attempt = attempt == ORDER_RETRY_COUNT

        # 재시도(또는 최종 실패 처리) 전에, 방금 요청이 실제로는 성공했는지
        # 먼저 확인합니다. 응답을 못 받았을 뿐 주문 자체는 들어갔을 수 있어,
        # 확인 없이 재시도하면 중복 주문으로 이어질 수 있습니다.
        existing = _find_recent_matching_order(upbit, market, side)
        if existing is not None:
            order_uuid = str(existing.get("uuid") or "")
            if order_uuid:
                return normalize_order_response(order_uuid, existing)

        if not is_last_attempt:
            time.sleep(ORDER_RETRY_DELAY_SECONDS)

    return LiveOrderResult(
        False,
        "failed",
        error_message=_error_message(last_response) if last_response else failure_message,
        raw_response=last_response,
    )


def execute_market_buy(
    *, access_key: str, secret_key: str, market: str, amount: float
) -> LiveOrderResult:
    """KRW 총액 기준 시장가 매수를 제출하고 짧게 체결 상태를 확인합니다.

    요청이 실패해도 곧바로 재시도하지 않고, 먼저 최근 체결 내역을 확인해
    실제로는 주문이 들어갔는지 확인한 뒤에만 안전하게 한 번 재시도합니다.
    """
    upbit = pyupbit.Upbit(access_key, secret_key)
    return _submit_with_retry(
        upbit=upbit,
        market=market,
        side="bid",
        submit=lambda: upbit.buy_market_order(market, amount),
        failure_message="Upbit 매수 주문 요청에 실패했습니다.",
    )


def execute_market_sell(
    *, access_key: str, secret_key: str, market: str, volume: float
) -> LiveOrderResult:
    """지정 수량만큼 시장가 매도를 제출하고 짧게 체결 상태를 확인합니다.

    요청이 실패해도 곧바로 재시도하지 않고, 먼저 최근 체결 내역을 확인해
    실제로는 주문이 들어갔는지 확인한 뒤에만 안전하게 한 번 재시도합니다.
    """
    upbit = pyupbit.Upbit(access_key, secret_key)
    return _submit_with_retry(
        upbit=upbit,
        market=market,
        side="ask",
        submit=lambda: upbit.sell_market_order(market, volume),
        failure_message="Upbit 매도 주문 요청에 실패했습니다.",
    )


def _resolve_order(upbit: pyupbit.Upbit, response: dict) -> LiveOrderResult:
    """주문 UUID를 짧게 조회해 체결량·평균가·최종 상태를 정규화합니다."""
    order_uuid = str(response["uuid"])
    order = response
    for _ in range(5):
        try:
            checked = upbit.get_order(order_uuid)
            if isinstance(checked, dict):
                order = checked
                if checked.get("state") in {"done", "cancel"}:
                    break
        except Exception:
            break
        time.sleep(1)

    return normalize_order_response(order_uuid, order)


def normalize_order_response(order_uuid: str, order: dict) -> LiveOrderResult:
    """Upbit 주문 조회 응답을 접수·부분 체결·완료·취소 상태로 정규화합니다."""
    state = str(order.get("state") or "wait")
    executed_volume = float(order.get("executed_volume") or 0) or None
    trades = order.get("trades") or []
    average_price = None
    paid_fee_value = order.get("paid_fee")
    paid_fee = float(paid_fee_value) if paid_fee_value is not None else None
    if trades:
        total_volume = sum((Decimal(str(item.get("volume") or 0)) for item in trades), Decimal("0"))
        total_funds = sum((Decimal(str(item.get("funds") or 0)) for item in trades), Decimal("0"))
        if total_volume > 0:
            average_price = float(total_funds / total_volume)

    # 시장가 주문은 요청 금액을 체결한 뒤 사용하지 못한 소액의 잔여 예약금을
    # 해제하면서 state=cancel로 종료될 수 있습니다. 체결 수량이 있으면 성공입니다.
    has_fill = bool(executed_volume and executed_volume > 0) or bool(trades)
    if state == "done":
        status = "success" if has_fill else "failed"
    elif state == "cancel":
        # 시장가 매수는 미사용 예약금이 취소되며 체결 수량이 있으면 정상 완료입니다.
        status = "success" if has_fill else "cancelled"
    else:
        status = "partially_filled" if has_fill else "submitted"

    return LiveOrderResult(
        success=status == "success",
        status=status,
        order_uuid=order_uuid,
        executed_volume=executed_volume,
        average_price=average_price,
        paid_fee=paid_fee,
        raw_response=order,
        error_message="체결 없이 주문이 취소되었습니다." if status == "cancelled" else None,
    )


def fetch_order_result(
    *, access_key: str, secret_key: str, order_uuid: str
) -> LiveOrderResult | None:
    """미완료 주문을 한 번 조회합니다. 일시적 조회 오류는 다음 주기에 재시도합니다."""
    try:
        response = pyupbit.Upbit(access_key, secret_key).get_order(order_uuid)
    except Exception:
        return None
    if not isinstance(response, dict):
        return None
    return normalize_order_response(order_uuid, response)

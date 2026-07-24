from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal

import pyupbit


@dataclass(frozen=True, slots=True)
class LiveOrderResult:
    success: bool
    status: str
    order_uuid: str | None = None
    executed_volume: float | None = None
    average_price: float | None = None
    error_message: str | None = None
    raw_response: dict | None = None


def _error_message(response: object) -> str:
    """형태가 일정하지 않은 Upbit 오류 응답에서 사용자용 사유를 추출합니다."""
    if isinstance(response, dict):
        error = response.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error.get("name") or "Upbit 주문이 거절되었습니다.")
    return "Upbit 주문 응답을 확인할 수 없습니다."


def execute_market_buy(
    *, access_key: str, secret_key: str, market: str, amount: float
) -> LiveOrderResult:
    """KRW 총액 기준 시장가 매수를 제출하고 짧게 체결 상태를 확인합니다."""
    upbit = pyupbit.Upbit(access_key, secret_key)
    try:
        response = upbit.buy_market_order(market, amount)
    except Exception:
        return LiveOrderResult(False, "failed", error_message="Upbit 매수 주문 요청에 실패했습니다.")

    if not isinstance(response, dict) or not response.get("uuid"):
        return LiveOrderResult(
            False,
            "failed",
            error_message=_error_message(response),
            raw_response=response if isinstance(response, dict) else None,
        )

    return _resolve_order(upbit, response)


def execute_market_sell(
    *, access_key: str, secret_key: str, market: str, volume: float
) -> LiveOrderResult:
    """지정 수량만큼 시장가 매도를 제출하고 짧게 체결 상태를 확인합니다."""
    upbit = pyupbit.Upbit(access_key, secret_key)
    try:
        response = upbit.sell_market_order(market, volume)
    except Exception:
        return LiveOrderResult(False, "failed", error_message="Upbit 매도 주문 요청에 실패했습니다.")

    if not isinstance(response, dict) or not response.get("uuid"):
        return LiveOrderResult(
            False,
            "failed",
            error_message=_error_message(response),
            raw_response=response if isinstance(response, dict) else None,
        )

    return _resolve_order(upbit, response)


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

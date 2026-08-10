from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Protocol

import pyupbit

from app.core.config import settings
from app.services.live_order import (
    LiveOrderResult,
    execute_market_buy,
    execute_market_sell,
    fetch_order_result,
)
from app.services.upbit import UpbitValidationResult, get_accounts, validate_upbit_api_key


class ExchangeAdapter(Protocol):
    """거래소별 외부 호출 경계입니다."""

    def validate_credentials(self, access_key: str, secret_key: str) -> UpbitValidationResult: ...
    def accounts(self, access_key: str, secret_key: str) -> list[dict]: ...
    def balances(self, access_key: str, secret_key: str) -> list[dict]: ...
    def buy_fee_rate(self, access_key: str, secret_key: str, market: str) -> Decimal: ...
    def market_buy(self, access_key: str, secret_key: str, market: str, amount: float, reference_price: float) -> LiveOrderResult: ...
    def market_sell(self, access_key: str, secret_key: str, market: str, volume: float, reference_price: float) -> LiveOrderResult: ...
    def order(self, access_key: str, secret_key: str, order_uuid: str) -> LiveOrderResult | None: ...


class UpbitExchangeAdapter:
    def validate_credentials(self, access_key: str, secret_key: str) -> UpbitValidationResult:
        return validate_upbit_api_key(access_key, secret_key, settings.upbit_api_base_url)

    def accounts(self, access_key: str, secret_key: str) -> list[dict]:
        return get_accounts(access_key, secret_key, settings.upbit_api_base_url)

    def balances(self, access_key: str, secret_key: str) -> list[dict]:
        response = pyupbit.Upbit(access_key, secret_key).get_balances()
        if not isinstance(response, list):
            raise ValueError("Upbit 계좌 조회에 실패했습니다. API 권한과 허용 IP를 확인해 주세요.")
        return response

    def buy_fee_rate(self, access_key: str, secret_key: str, market: str) -> Decimal:
        response = pyupbit.Upbit(access_key, secret_key).get_chance(market)
        if not isinstance(response, dict):
            raise ValueError("Upbit 주문 가능 정보를 조회할 수 없습니다.")
        return Decimal(str(response["bid_fee"]))

    def market_buy(self, access_key: str, secret_key: str, market: str, amount: float, reference_price: float) -> LiveOrderResult:
        return execute_market_buy(access_key=access_key, secret_key=secret_key, market=market, amount=amount)

    def market_sell(self, access_key: str, secret_key: str, market: str, volume: float, reference_price: float) -> LiveOrderResult:
        return execute_market_sell(access_key=access_key, secret_key=secret_key, market=market, volume=volume)

    def order(self, access_key: str, secret_key: str, order_uuid: str) -> LiveOrderResult | None:
        return fetch_order_result(access_key=access_key, secret_key=secret_key, order_uuid=order_uuid)


class FakeExchangeAdapter:
    """부하테스트에서 네트워크나 실제 자산 없이 실전 주문 경로를 실행합니다."""

    def validate_credentials(self, access_key: str, secret_key: str) -> UpbitValidationResult:
        return UpbitValidationResult(bool(access_key and secret_key), "유효한 Fake Exchange API Key입니다.")

    def accounts(self, access_key: str, secret_key: str) -> list[dict]:
        return [
            {
                "currency": "KRW",
                "balance": str(settings.fake_exchange_krw_balance),
                "locked": "0",
                "avg_buy_price": "0",
                "avg_buy_price_modified": False,
                "unit_currency": "KRW",
            }
        ]

    def balances(self, access_key: str, secret_key: str) -> list[dict]:
        return self.accounts(access_key, secret_key)

    def buy_fee_rate(self, access_key: str, secret_key: str, market: str) -> Decimal:
        return Decimal(str(settings.fake_exchange_fee_rate))

    def market_buy(self, access_key: str, secret_key: str, market: str, amount: float, reference_price: float) -> LiveOrderResult:
        volume = amount / reference_price if reference_price > 0 else 0
        return self._filled(volume, reference_price)

    def market_sell(self, access_key: str, secret_key: str, market: str, volume: float, reference_price: float) -> LiveOrderResult:
        return self._filled(volume, reference_price)

    def order(self, access_key: str, secret_key: str, order_uuid: str) -> LiveOrderResult | None:
        return LiveOrderResult(True, "success", order_uuid=order_uuid)

    @staticmethod
    def _filled(volume: float, price: float) -> LiveOrderResult:
        order_uuid = f"fake-{uuid.uuid4()}"
        return LiveOrderResult(
            True,
            "success",
            order_uuid=order_uuid,
            executed_volume=volume,
            average_price=price,
            raw_response={"uuid": order_uuid, "state": "done", "provider": "fake"},
        )


_UPBIT_ADAPTER = UpbitExchangeAdapter()
_FAKE_ADAPTER = FakeExchangeAdapter()


def get_exchange_adapter() -> ExchangeAdapter:
    if settings.exchange_adapter == "upbit":
        return _UPBIT_ADAPTER
    if settings.exchange_adapter == "fake":
        return _FAKE_ADAPTER
    raise RuntimeError(f"지원하지 않는 EXCHANGE_ADAPTER입니다: {settings.exchange_adapter}")

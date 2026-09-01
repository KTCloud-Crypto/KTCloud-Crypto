import asyncio
from types import SimpleNamespace

import pytest

from app.portfolio import api as positions


class _SupportedMarketQuery:
    def __init__(self, codes: list[str]) -> None:
        self.codes = codes

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return [SimpleNamespace(code=code) for code in self.codes]


class _AccountStatusDb:
    def __init__(self, supported_codes: list[str]) -> None:
        self.supported_codes = supported_codes

    def query(self, _model):
        return _SupportedMarketQuery(self.supported_codes)


class _ApiKeyQuery:
    def __init__(self, api_key) -> None:
        self.api_key = api_key

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.api_key


class _AccountLoadDb:
    def __init__(self) -> None:
        self.info = {}
        self.api_key = SimpleNamespace(id=1, user_id=7)

    def query(self, _model):
        return _ApiKeyQuery(self.api_key)


def test_account_load_is_shared_within_dashboard_request(monkeypatch) -> None:
    """대시보드 조립 함수들이 같은 DB 세션에서는 Upbit accounts를 한 번만 조회합니다."""
    db = _AccountLoadDb()
    calls = []
    accounts = [{"currency": "KRW", "balance": "10000", "locked": "0"}]
    monkeypatch.setattr(positions, "resolve_exchange_credentials", lambda _key: ("a", "s"))

    def load_accounts(**_kwargs):
        calls.append(1)
        return accounts

    monkeypatch.setattr(positions, "get_accounts", load_accounts)

    first = positions._load_accounts(db, user_id=7)
    second = positions._load_accounts(db, user_id=7)

    assert first is accounts
    assert second is accounts
    assert len(calls) == 1


def test_account_status_includes_unsupported_coin_and_locked_assets(monkeypatch) -> None:
    """자동매매 미지원 코인도 실제 계좌 자산과 미배정 평가액에는 포함합니다."""
    btc_position = SimpleNamespace(
        subscription=SimpleNamespace(id=11),
        strategy=SimpleNamespace(id=2, name="이동평균 교차 전략"),
        market="KRW-BTC",
        volume=0.7,
    )
    monkeypatch.setattr(positions, "recorded_strategy_positions", lambda *_args: [btc_position])
    monkeypatch.setattr(positions, "recorded_strategy_volumes", lambda *_args: {"BTC": 0.7})
    monkeypatch.setattr(positions, "reserved_amount", lambda *_args: 1_000)

    async def price(market: str) -> float:
        return {"KRW-BTC": 100.0, "KRW-ADA": 200.0}[market]

    monkeypatch.setattr(positions, "get_current_price", price)
    accounts = [
        {"currency": "KRW", "balance": "10000", "locked": "500", "avg_buy_price": "0"},
        {"currency": "BTC", "balance": "0.4", "locked": "0.6", "avg_buy_price": "80"},
        {"currency": "ADA", "balance": "2", "locked": "1", "avg_buy_price": "150"},
    ]

    status = asyncio.run(positions._account_status(
        _AccountStatusDb(["KRW-BTC"]),
        user_id=1,
        accounts=accounts,
    ))

    assert status.available_krw == 10_000
    assert status.locked_krw == 500
    assert status.total_krw == 10_500
    assert status.coin_evaluation_amount == pytest.approx(700)
    assert status.account_equity == pytest.approx(11_200)
    assert status.managed_positions_value == pytest.approx(70)
    assert status.unallocated_value == pytest.approx(630)

    assets = {item.currency: item for item in status.assets}
    assert assets["BTC"].total == pytest.approx(1.0)
    assert assets["BTC"].unallocated_volume == pytest.approx(0.3)
    assert assets["BTC"].reconciliation_status == "external_balance"
    assert assets["ADA"].supported is False
    assert assets["ADA"].market is None
    assert assets["ADA"].total == pytest.approx(3.0)
    assert assets["ADA"].unallocated_value == pytest.approx(600)


def test_account_status_keeps_unknown_price_asset_without_inventing_value(monkeypatch) -> None:
    """KRW 현재가가 없는 코인은 수량만 보존하고 총평가액에는 임의 반영하지 않습니다."""
    monkeypatch.setattr(positions, "recorded_strategy_positions", lambda *_args: [])
    monkeypatch.setattr(positions, "recorded_strategy_volumes", lambda *_args: {})
    monkeypatch.setattr(positions, "reserved_amount", lambda *_args: 0)

    async def unavailable_price(_market: str) -> float:
        raise RuntimeError("KRW market unavailable")

    monkeypatch.setattr(positions, "get_current_price", unavailable_price)
    accounts = [
        {"currency": "KRW", "balance": "10000", "locked": "0", "avg_buy_price": "0"},
        {"currency": "XYZ", "balance": "5", "locked": "2", "avg_buy_price": "1"},
    ]

    status = asyncio.run(positions._account_status(
        _AccountStatusDb([]),
        user_id=1,
        accounts=accounts,
    ))

    assert status.account_equity == 10_000
    assert status.unallocated_value == 0
    assert status.assets[0].currency == "XYZ"
    assert status.assets[0].total == 7
    assert status.assets[0].current_price is None
    assert status.assets[0].evaluation_amount is None
    assert status.assets[0].unallocated_volume == 7
    assert status.assets[0].unallocated_value is None

from decimal import Decimal
from unittest.mock import patch
 
from app.services.execution_preflight import (
    MIN_KRW_ORDER,
    fee_adjusted_buying_power,
    validate_order_readiness,
)
from app.services.strategy_allocation import budget_for_buy, snapshot_allocation
 
 
def test_snapshot_uses_free_cash_only() -> None:
    """예산은 가용 현금에서 다른 전략이 확보한 금액을 뺀 자유 현금 기준으로 잡습니다."""
    assert snapshot_allocation(
        available_cash="1000000",
        reserved="0",
        invest_ratio=0.5,
    ) == Decimal("500000")
 
 
def test_snapshot_excludes_other_strategy_reservations() -> None:
    """다른 전략이 이미 확보한 예산은 자유 현금에서 제외됩니다."""
    assert snapshot_allocation(
        available_cash="1000000",
        reserved="600000",
        invest_ratio=0.5,
    ) == Decimal("200000")
 
 
def test_snapshot_never_goes_negative() -> None:
    """확보된 예산이 현금을 넘어도 음수가 되지 않습니다."""
    assert snapshot_allocation(
        available_cash="500000",
        reserved="800000",
        invest_ratio=0.5,
    ) == Decimal("0")
 
 
def test_budget_uses_allocated_amount_when_present() -> None:
    """확정된 예산이 있으면 현재 현금과 무관하게 그 금액을 사용합니다."""
    assert budget_for_buy(
        allocated_amount=300_000,
        available_cash="1000000",
        invest_ratio=0.5,
    ) == Decimal("300000")
 
 
def test_budget_is_capped_by_available_cash() -> None:
    """확정 예산이 남은 현금보다 크면 현금 범위로 제한됩니다."""
    assert budget_for_buy(
        allocated_amount=800_000,
        available_cash="300000",
        invest_ratio=0.5,
    ) == Decimal("300000")
 
 
def test_budget_falls_back_to_ratio_when_not_allocated() -> None:
    """예산이 아직 없는 기존 구독은 현재 현금에 비율을 적용합니다."""
    assert budget_for_buy(
        allocated_amount=None,
        available_cash="1000000",
        invest_ratio=0.3,
    ) == Decimal("300000")
 
 
@patch("app.services.execution_preflight.resolve_exchange_credentials", return_value=("a", "s"))
@patch(
    "app.services.execution_preflight._buy_fee_rate",
    return_value=Decimal("0.0005"),
)
@patch(
    "app.services.execution_preflight._available_balances",
    return_value={"KRW": Decimal("500000")},
)
def test_live_preflight_uses_allocated_amount(
    _balances,
    _fee_rate,
    _credentials,
) -> None:
    """확정된 예산이 있으면 보유 포지션과 무관하게 그 금액으로 주문합니다."""
    result = validate_order_readiness(
        api_key=None,
        action="buy",
        market="KRW-BTC",
        reference_price=100_000_000,
        invest_ratio=0.5,
        allocated_amount=400_000,
    )
    assert result.ready is True
    assert result.order_amount == 400_000
 
 
@patch("app.services.execution_preflight.resolve_exchange_credentials", return_value=("a", "s"))
@patch(
    "app.services.execution_preflight._buy_fee_rate",
    return_value=Decimal("0.0005"),
)
@patch(
    "app.services.execution_preflight._available_balances",
    return_value={"KRW": Decimal("500000")},
)
def test_live_preflight_falls_back_to_cash_ratio(
    _balances,
    _fee_rate,
    _credentials,
) -> None:
    """예산이 없으면 현재 KRW 현금에 비율을 적용합니다."""
    result = validate_order_readiness(
        api_key=None,
        action="buy",
        market="KRW-BTC",
        reference_price=100_000_000,
        invest_ratio=0.5,
        allocated_amount=None,
    )
    assert result.ready is True
    assert result.order_amount == 250_000
 
 
@patch("app.services.execution_preflight.resolve_exchange_credentials", return_value=("a", "s"))
@patch(
    "app.services.execution_preflight._buy_fee_rate",
    return_value=Decimal("0.0005"),
)
@patch(
    "app.services.execution_preflight._available_balances",
    return_value={"KRW": Decimal("500000")},
)
def test_live_preflight_reserves_fee_from_full_cash_order(
    _balances,
    _fee_rate,
    _credentials,
) -> None:
    """예산이 현금 전액이어도 수수료만큼은 남겨둡니다."""
    result = validate_order_readiness(
        api_key=None,
        action="buy",
        market="KRW-BTC",
        reference_price=100_000_000,
        invest_ratio=1.0,
        allocated_amount=500_000,
    )
    assert result.ready is True
    assert result.order_amount == 499_749
 
 
def test_buying_power_reserves_fee_and_one_won() -> None:
    amount = fee_adjusted_buying_power(
        available_krw=Decimal("6072"),
        fee_rate=Decimal("0.0005"),
    )
    assert amount == Decimal("6067")
 
 
def test_minimum_krw_order_is_5000() -> None:
    assert MIN_KRW_ORDER == Decimal("5000")
 
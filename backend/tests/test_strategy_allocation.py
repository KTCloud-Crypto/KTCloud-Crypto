from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from app.services.strategy_allocation import cash_funded_subscription_ids, reserved_amount


class _SubscriptionQuery:
    def __init__(self, subscriptions: list[SimpleNamespace]) -> None:
        self.subscriptions = subscriptions

    def filter(self, *_args, **_kwargs):
        return self

    def all(self) -> list[SimpleNamespace]:
        return self.subscriptions


class _AllocationDb:
    def __init__(self, subscriptions: list[SimpleNamespace]) -> None:
        self.subscriptions = subscriptions

    def query(self, *_models):
        return _SubscriptionQuery(self.subscriptions)


def test_deducted_flat_position_is_reserved_for_the_next_buy() -> None:
    """체결 원장에 잔량이 있어도 deduct 후 최종 포지션이 0이면 예산을 다시 예약합니다."""
    subscriptions = [
        SimpleNamespace(id=34, allocated_amount=13_884.58),
        SimpleNamespace(id=80, allocated_amount=10_083.91),
    ]
    db = _AllocationDb(subscriptions)

    with patch(
        "app.services.strategy_allocation.load_strategy_position",
        return_value=SimpleNamespace(volume=0),
    ) as load_position:
        reserved = reserved_amount(db, user_id=3, mode="live")

    assert reserved == Decimal("23968.49")
    assert [call.args[1] for call in load_position.call_args_list] == [34, 80]


def test_only_final_positions_with_volume_are_cash_funded() -> None:
    subscriptions = [
        SimpleNamespace(id=34, allocated_amount=13_884.58),
        SimpleNamespace(id=80, allocated_amount=10_083.91),
    ]
    db = _AllocationDb(subscriptions)

    def final_position(_db, subscription_id: int, _mode: str):
        return SimpleNamespace(volume=0.0001 if subscription_id == 80 else 0)

    with patch(
        "app.services.strategy_allocation.load_strategy_position",
        side_effect=final_position,
    ):
        funded = cash_funded_subscription_ids(db, user_id=3, mode="live")

    assert funded == frozenset({80})

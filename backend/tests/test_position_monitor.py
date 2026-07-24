from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.position_mismatch import PositionMismatchIncident
from app.services import position_monitor


def _db_with_incidents(incidents: list[PositionMismatchIncident]) -> MagicMock:
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = incidents
    return db


def test_mismatch_notification_explains_no_automatic_order() -> None:
    text = position_monitor.mismatch_notification_text("BTC", "external_balance", 0.2, 0.1, 0.1)

    assert "외부 보유 수량" in text
    assert "/sync" in text
    assert "자동으로 주문" in text


def test_existing_incident_is_updated_without_duplicate_notification(monkeypatch) -> None:
    incident = PositionMismatchIncident(
        user_id=1,
        currency="BTC",
        mismatch_type="external_balance",
        actual_total=0.2,
        strategy_volume=0.1,
        difference=0.1,
        notified_at=datetime(2026, 1, 1),
    )
    db = _db_with_incidents([incident])
    send = MagicMock()
    monkeypatch.setattr(position_monitor, "send_message", send)

    count = position_monitor._record_currency_state(
        db,
        SimpleNamespace(id=1, telegram_chat_id="123"),
        "BTC",
        0.25,
        0.1,
        datetime(2026, 1, 2),
    )

    assert count == 0
    assert incident.difference == 0.15
    send.assert_not_called()


def test_incident_is_resolved_when_balances_match() -> None:
    incident = PositionMismatchIncident(
        user_id=1,
        currency="BTC",
        mismatch_type="shortfall",
        actual_total=0.05,
        strategy_volume=0.1,
        difference=-0.05,
    )
    db = _db_with_incidents([incident])
    now = datetime(2026, 1, 2)

    count = position_monitor._record_currency_state(
        db,
        SimpleNamespace(id=1, telegram_chat_id="123"),
        "BTC",
        0.1,
        0.1,
        now,
    )

    assert count == 0
    assert incident.resolved_at == now

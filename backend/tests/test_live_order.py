from unittest.mock import patch

from app.services.live_order import _error_message, execute_market_buy, normalize_order_response


def test_upbit_error_message_is_extracted() -> None:
    response = {"error": {"name": "insufficient_funds_bid", "message": "잔고가 부족합니다."}}
    assert _error_message(response) == "잔고가 부족합니다."


@patch("app.services.live_order.pyupbit.Upbit")
def test_market_buy_cancel_with_executed_volume_is_success(mock_upbit_class) -> None:
    client = mock_upbit_class.return_value
    client.buy_market_order.return_value = {"uuid": "order-1", "state": "wait"}
    client.get_order.return_value = {
        "uuid": "order-1",
        "state": "cancel",
        "executed_volume": "0.00005639",
        "paid_fee": "2.73497139",
        "trades": [{"volume": "0.00005639", "funds": "5469.94278"}],
    }

    result = execute_market_buy(
        access_key="access", secret_key="secret", market="KRW-BTC", amount=5470
    )

    assert result.success is True
    assert result.status == "success"
    assert result.executed_volume == 0.00005639
    assert result.paid_fee == 2.73497139
    assert result.error_message is None


@patch("app.services.live_order.pyupbit.Upbit")
def test_market_sell_with_executed_volume_is_success(mock_upbit_class) -> None:
    client = mock_upbit_class.return_value
    client.sell_market_order.return_value = {"uuid": "sell-1", "state": "wait"}
    client.get_order.return_value = {
        "uuid": "sell-1",
        "state": "done",
        "executed_volume": "0.00005639",
        "trades": [{"volume": "0.00005639", "funds": "5450"}],
    }

    from app.services.live_order import execute_market_sell

    result = execute_market_sell(
        access_key="access", secret_key="secret", market="KRW-BTC", volume=0.00005639
    )

    client.sell_market_order.assert_called_once_with("KRW-BTC", 0.00005639)
    assert result.status == "success"
    assert result.executed_volume == 0.00005639


def test_waiting_order_with_fill_is_partially_filled() -> None:
    result = normalize_order_response(
        "partial-1",
        {
            "state": "wait",
            "executed_volume": "0.00001",
            "paid_fee": "0.48",
            "trades": [{"volume": "0.00001", "funds": "960"}],
        },
    )
    assert result.status == "partially_filled"
    assert result.success is False
    assert result.executed_volume == 0.00001
    assert result.average_price == 96_000_000
    assert result.paid_fee == 0.48


def test_cancelled_order_without_fill_is_cancelled() -> None:
    result = normalize_order_response(
        "cancel-1",
        {"state": "cancel", "executed_volume": "0", "trades": []},
    )
    assert result.status == "cancelled"
    assert result.success is False
    assert result.error_message == "체결 없이 주문이 취소되었습니다."

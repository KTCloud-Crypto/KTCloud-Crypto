import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.telegram_poller import TelegramPoller, _apply_sync_callback, _find_id_text, _help_text


def _message_update(text: str) -> dict:
    return {
        "update_id": 1,
        "message": {
            "text": text,
            "chat": {"id": 1234},
        },
    }


def test_help_lists_core_commands() -> None:
    text = _help_text()
    for command in ("/status", "/pause", "/resume", "/balance", "/positions", "/sync", "/findid"):
        assert command in text


def test_find_id_uses_linked_telegram_chat() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(username="signal_user")
    with patch("app.services.telegram_poller.SessionLocal", return_value=db):
        text = _find_id_text("unique-find-id-chat")
    assert "signal_user" in text
    db.close.assert_called_once()


def test_find_id_is_blocked_in_group_chat() -> None:
    poller = TelegramPoller("test-token")
    poller._send_message = AsyncMock()
    update = _message_update("/findid")
    update["message"]["chat"]["type"] = "group"
    asyncio.run(poller._handle_update(AsyncMock(), update))
    assert "개인 채팅" in poller._send_message.await_args.args[2]


def test_unknown_slash_command_guides_user_to_help() -> None:
    poller = TelegramPoller("test-token")
    poller._send_message = AsyncMock()

    asyncio.run(
        poller._handle_update(
            AsyncMock(),
            _message_update("/unknown"),
        )
    )

    sent_text = poller._send_message.await_args.args[2]
    assert "등록되지 않은 명령어" in sent_text
    assert "/help" in sent_text


def test_non_command_message_is_ignored() -> None:
    poller = TelegramPoller("test-token")
    poller._send_message = AsyncMock()

    asyncio.run(
        poller._handle_update(
            AsyncMock(),
            _message_update("안녕하세요"),
        )
    )

    poller._send_message.assert_not_awaited()


def test_close_requires_selection_and_confirmation() -> None:
    poller = TelegramPoller("test-token")
    poller._send_message = AsyncMock()

    async def scenario() -> None:
        with patch(
            "app.services.telegram_poller._close_menu",
            return_value="매도할 포지션을 선택해 주세요.",
        ), patch(
            "app.services.telegram_poller._prepare_close",
            return_value=("최종 확인", (10,)),
        ), patch(
            "app.services.telegram_poller._execute_close",
            new=AsyncMock(return_value="매도 요청 완료"),
        ) as execute:
            await poller._handle_update(AsyncMock(), _message_update("/close"))
            await poller._handle_update(AsyncMock(), _message_update("/live_sma"))
            execute.assert_not_awaited()
            await poller._handle_update(AsyncMock(), _message_update("/confirm"))
            execute.assert_awaited_once_with("1234", (10,))

    asyncio.run(scenario())


def test_position_sync_callback_uses_user_strategy_subscription_id() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=1)
    selected = SimpleNamespace(
        subscription=SimpleNamespace(id=77),
        strategy=SimpleNamespace(id=9, name="이동평균"),
        market="KRW-BTC",
        volume=0.00006312,
    )
    accounts = [{"currency": "BTC", "balance": "0", "locked": "0"}]
    adjustment = SimpleNamespace(volume=0.00006312)

    with patch("app.services.telegram_poller.SessionLocal", return_value=db), patch(
        "app.services.telegram_poller._accounts_for_user", return_value=accounts,
    ), patch(
        "app.services.telegram_poller.recorded_strategy_positions", return_value=[selected],
    ), patch(
        "app.services.telegram_poller.recorded_strategy_volumes", return_value={"BTC": 0.00006312},
    ), patch(
        "app.services.telegram_poller.apply_position_sync", return_value=adjustment,
    ) as apply_sync:
        reply = _apply_sync_callback("1234", "deduct", "BTC", 77)

    assert "이동평균" in reply
    apply_sync.assert_called_once_with(
        db,
        user_id=1,
        accounts=accounts,
        subscription_id=77,
        action="deduct",
        volume=0.00006312,
        source="telegram",
    )
    db.close.assert_called_once()


def test_position_sync_callback_is_idempotent_after_sync() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=1)
    selected = SimpleNamespace(
        subscription=SimpleNamespace(id=77),
        strategy=SimpleNamespace(id=9, name="미배정 자산"),
        market="KRW-BTC",
        volume=0.00006312,
    )
    accounts = [{"currency": "BTC", "balance": "0.00006312", "locked": "0"}]

    with patch("app.services.telegram_poller.SessionLocal", return_value=db), patch(
        "app.services.telegram_poller._accounts_for_user", return_value=accounts,
    ), patch(
        "app.services.telegram_poller.recorded_strategy_positions", return_value=[selected],
    ), patch(
        "app.services.telegram_poller.recorded_strategy_volumes",
        return_value={"BTC": 0.00006312},
    ), patch("app.services.telegram_poller.apply_position_sync") as apply_sync:
        reply = _apply_sync_callback("1234", "deduct", "BTC", 77)

    assert "이미" in reply
    apply_sync.assert_not_called()
    db.close.assert_called_once()

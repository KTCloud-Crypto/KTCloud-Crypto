import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.telegram_poller import TelegramPoller, _find_id_text, _help_text


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
    for command in ("/status", "/pause", "/resume", "/balance", "/positions", "/findid"):
        assert command in text
    assert "/sync" not in text


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

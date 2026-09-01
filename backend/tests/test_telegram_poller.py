import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.notification.poller import TelegramPoller, _find_id_text, _help_text, _link_chat, _set_pause


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
    with patch("app.notification.poller.SessionLocal", return_value=db):
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


def test_link_chat_delegates_to_identity_api_without_local_db() -> None:
    with patch("app.notification.poller.link_telegram_chat", return_value=True) as link:
        assert _link_chat("ABCD2345", "chat-1") is True

    link.assert_called_once_with("ABCD2345", "chat-1")


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
            "app.notification.poller._close_menu",
            return_value="매도할 포지션을 선택해 주세요.",
        ), patch(
            "app.notification.poller._prepare_close",
            return_value=("최종 확인", (10,)),
        ), patch(
            "app.notification.poller._execute_close",
            new=AsyncMock(return_value="매도 요청 완료"),
        ) as execute:
            await poller._handle_update(AsyncMock(), _message_update("/close"))
            await poller._handle_update(AsyncMock(), _message_update("/live_sma"))
            execute.assert_not_awaited()
            await poller._handle_update(AsyncMock(), _message_update("/confirm"))
            execute.assert_awaited_once_with("1234", (10,))

    asyncio.run(scenario())


def test_pause_command_delegates_to_strategy_api_without_committing() -> None:
    db = MagicMock()
    user = SimpleNamespace(id=7)
    subscription = SimpleNamespace(id=11, mode="live", paused=False)
    strategy = SimpleNamespace(code="rsi_reversal_v1", name="RSI")
    market = SimpleNamespace(code="KRW-BTC")
    with (
        patch("app.notification.poller.SessionLocal", return_value=db),
        patch("app.notification.poller._linked_user", return_value=user),
        patch(
            "app.notification.poller._strategy_rows",
            return_value=[(subscription, strategy, market)],
        ),
        patch("app.notification.poller.set_subscriptions_paused", return_value=1) as change,
    ):
        text = _set_pause("chat-1", "pause", "live_btc_rsi")

    assert "신규 매수를 일시정지" in text
    change.assert_called_once()
    assert list(change.call_args.kwargs["subscription_ids"]) == [11]
    assert change.call_args.kwargs["user_id"] == 7
    assert change.call_args.kwargs["paused"] is True
    db.commit.assert_not_called()

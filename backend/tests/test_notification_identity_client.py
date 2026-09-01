from unittest.mock import MagicMock, patch

import httpx

from app.notification.identity_client import link_telegram_chat


def test_notification_uses_identity_http_api_for_telegram_link() -> None:
    response = MagicMock()
    response.json.return_value = {"linked": True}
    with patch("app.notification.identity_client.httpx.post", return_value=response) as post:
        assert link_telegram_chat("ABCD2345", "chat-1") is True

    assert post.call_args.args[0].endswith("/internal/telegram-links")
    assert post.call_args.kwargs["json"] == {"code": "ABCD2345", "chat_id": "chat-1"}


def test_notification_treats_identity_transport_failure_as_unlinked() -> None:
    with patch(
        "app.notification.identity_client.httpx.post",
        side_effect=httpx.ConnectError("down"),
    ):
        assert link_telegram_chat("ABCD2345", "chat-1") is False

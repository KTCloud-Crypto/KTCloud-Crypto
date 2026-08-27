from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.api.auth import notify_login_lockout
from app.schemas.auth import SignupRequest
from app.identity import LoginAttemptGuard, SimpleRateLimiter


def test_login_guard_locks_after_repeated_failures() -> None:
    guard = LoginAttemptGuard(max_failures=2, lockout_minutes=5)
    now = datetime(2024, 1, 1, 12, 0, 0)

    assert guard.allow("alice", now=now) is True
    guard.record_failure("alice", now=now)
    guard.record_failure("alice", now=now)

    assert guard.is_locked("alice", now=now) is True
    assert guard.allow("alice", now=now) is False


def test_login_guard_releases_after_lockout_window() -> None:
    guard = LoginAttemptGuard(max_failures=2, lockout_minutes=5)
    now = datetime(2024, 1, 1, 12, 0, 0)

    guard.record_failure("bob", now=now)
    guard.record_failure("bob", now=now)

    assert guard.is_locked("bob", now=now) is True
    assert guard.allow("bob", now=now + timedelta(minutes=6)) is True


def test_simple_rate_limiter_blocks_over_limit() -> None:
    limiter = SimpleRateLimiter(window_seconds=60, max_requests=2)
    now = datetime(2024, 1, 1, 12, 0, 0)

    assert limiter.allow("10.0.0.1", now=now) is True
    assert limiter.allow("10.0.0.1", now=now) is True
    assert limiter.allow("10.0.0.1", now=now) is False


@patch("app.api.auth.send_message")
def test_notify_login_lockout_sends_telegram_message(mock_send_message: object) -> None:
    user = SimpleNamespace(telegram_chat_id="123456")

    notify_login_lockout(user, lockout_minutes=10)

    mock_send_message.assert_called_once()
    message = mock_send_message.call_args[0][1]
    assert "계정 잠금 안내" in message
    assert "10분" in message


def test_signup_allows_missing_exchange_key() -> None:
    payload = SignupRequest(
        username="paper_user",
        password="Password1",
        nickname="모의투자",
    )

    assert payload.access_key is None
    assert payload.secret_key is None


def test_signup_requires_complete_exchange_key_pair() -> None:
    with pytest.raises(ValidationError):
        SignupRequest(
            username="paper_user",
            password="Password1",
            nickname="모의투자",
            access_key="access-key-value",
        )

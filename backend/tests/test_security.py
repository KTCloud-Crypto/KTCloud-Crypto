from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.identity.api_auth import notify_login_lockout
from app.schemas.auth import SignupRequest
from app.identity import LoginAttemptGuard, SimpleRateLimiter
from app.identity.redis_state import RedisSecurityState


class SharedFakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    def eval(self, script, key_count, key, ttl):
        del script, key_count, ttl
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def get(self, key):
        return self.values.get(key)

    def delete(self, key):
        self.values.pop(key, None)

    def ping(self):
        return True


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


def test_login_guard_state_is_shared_between_identity_replicas() -> None:
    redis = SharedFakeRedis()
    first = LoginAttemptGuard(max_failures=2, state=RedisSecurityState(redis))
    second = LoginAttemptGuard(max_failures=2, state=RedisSecurityState(redis))

    first.record_failure("shared-user")
    second.record_failure("shared-user")

    assert first.is_locked("shared-user") is True
    assert second.is_locked("shared-user") is True


def test_rate_limit_state_is_shared_between_identity_replicas() -> None:
    redis = SharedFakeRedis()
    first = SimpleRateLimiter(max_requests=2, state=RedisSecurityState(redis))
    second = SimpleRateLimiter(max_requests=2, state=RedisSecurityState(redis))

    assert first.allow("shared-client") is True
    assert second.allow("shared-client") is True
    assert first.allow("shared-client") is False


@patch("app.identity.api_auth.enqueue_notification_requested")
def test_notify_login_lockout_queues_notification(mock_enqueue: object) -> None:
    db = MagicMock()
    user = SimpleNamespace(id=7, telegram_chat_id="123456")

    notify_login_lockout(db, user, lockout_minutes=10)

    mock_enqueue.assert_called_once()
    message = mock_enqueue.call_args.kwargs["message"]
    assert "계정 잠금 안내" in message
    assert "10분" in message
    db.commit.assert_called_once()


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

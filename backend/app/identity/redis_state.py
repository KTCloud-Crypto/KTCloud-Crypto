from __future__ import annotations

import hashlib
import json
from collections import deque
from threading import Lock
from typing import Any, Protocol

from redis import Redis

from app.core.config import settings


_INCREMENT_WITH_TTL = """
local value = redis.call('incr', KEYS[1])
if value == 1 then
  redis.call('expire', KEYS[1], ARGV[1])
end
return value
"""


class SecurityState(Protocol):
    def ping(self) -> bool: ...
    def increment(self, namespace: str, key: str, *, ttl_seconds: int, now_timestamp: float | None = None) -> int: ...
    def count(self, namespace: str, key: str, *, now_timestamp: float | None = None) -> int: ...
    def reset(self, namespace: str, key: str) -> None: ...
    def add_event(self, event: dict[str, Any], *, max_events: int) -> None: ...
    def recent_events(self) -> list[dict[str, Any]]: ...


class RedisSecurityState:
    """Identity Pod들이 공유하는 잠금·rate limit·임시 보안 이벤트 상태입니다."""

    def __init__(self, client: Redis, *, prefix: str = "signaltrade:identity") -> None:
        self._client = client
        self._prefix = prefix

    @classmethod
    def from_settings(cls) -> "RedisSecurityState":
        return cls(
            Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
        )

    def _counter_key(self, namespace: str, key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return f"{self._prefix}:{namespace}:{digest}"

    def ping(self) -> bool:
        return bool(self._client.ping())

    def increment(self, namespace: str, key: str, *, ttl_seconds: int, now_timestamp: float | None = None) -> int:
        del now_timestamp
        redis_key = self._counter_key(namespace, key)
        return int(self._client.eval(_INCREMENT_WITH_TTL, 1, redis_key, ttl_seconds))

    def count(self, namespace: str, key: str, *, now_timestamp: float | None = None) -> int:
        del now_timestamp
        value = self._client.get(self._counter_key(namespace, key))
        return int(value or 0)

    def reset(self, namespace: str, key: str) -> None:
        self._client.delete(self._counter_key(namespace, key))

    def add_event(self, event: dict[str, Any], *, max_events: int) -> None:
        event_key = f"{self._prefix}:security-events"
        pipeline = self._client.pipeline(transaction=True)
        pipeline.lpush(event_key, json.dumps(event, ensure_ascii=False, separators=(",", ":")))
        pipeline.ltrim(event_key, 0, max_events - 1)
        pipeline.expire(event_key, settings.security_event_retention_seconds)
        pipeline.execute()

    def recent_events(self) -> list[dict[str, Any]]:
        values = self._client.lrange(f"{self._prefix}:security-events", 0, -1)
        return [json.loads(value) for value in values]


class InMemorySecurityState:
    """외부 infrastructure를 사용하지 않는 단위 테스트용 동일 계약 구현입니다."""

    def __init__(self) -> None:
        self._counts: dict[tuple[str, str], tuple[int, float]] = {}
        self._events: deque[dict[str, Any]] = deque()
        self._lock = Lock()

    def ping(self) -> bool:
        return True

    def increment(self, namespace: str, key: str, *, ttl_seconds: int, now_timestamp: float | None = None) -> int:
        import time
        now_timestamp = time.time() if now_timestamp is None else now_timestamp
        with self._lock:
            state_key = (namespace, key)
            count, expires_at = self._counts.get(state_key, (0, 0.0))
            if expires_at <= now_timestamp:
                count = 0
                expires_at = now_timestamp + ttl_seconds
            count += 1
            self._counts[state_key] = (count, expires_at)
            return count

    def count(self, namespace: str, key: str, *, now_timestamp: float | None = None) -> int:
        import time
        now_timestamp = time.time() if now_timestamp is None else now_timestamp
        with self._lock:
            state_key = (namespace, key)
            count, expires_at = self._counts.get(state_key, (0, 0.0))
            if expires_at <= now_timestamp:
                self._counts.pop(state_key, None)
                return 0
            return count

    def reset(self, namespace: str, key: str) -> None:
        with self._lock:
            self._counts.pop((namespace, key), None)

    def add_event(self, event: dict[str, Any], *, max_events: int) -> None:
        with self._lock:
            self._events.appendleft(event)
            while len(self._events) > max_events:
                self._events.pop()

    def recent_events(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)


identity_security_state: SecurityState = (
    InMemorySecurityState()
    if settings.environment.lower() == "test"
    else RedisSecurityState.from_settings()
)

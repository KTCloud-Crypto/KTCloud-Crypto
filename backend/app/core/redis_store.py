from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from redis import Redis

from app.core.config import settings


_RELEASE_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


class RedisStore:
    """재생성 가능한 cache와 짧은 수명의 분산 lock만 제공합니다."""

    def __init__(self, client: Redis, *, namespace: str = "signaltrade") -> None:
        self._client = client
        self._namespace = namespace.strip(":")

    @classmethod
    def from_settings(cls) -> "RedisStore":
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        return cls(client)

    def _key(self, key: str) -> str:
        return f"{self._namespace}:{key}"

    def ping(self) -> bool:
        return bool(self._client.ping())

    def set_json(self, key: str, value: Any, *, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        self._client.set(
            self._key(key),
            json.dumps(value, ensure_ascii=False, separators=(",", ":")),
            ex=ttl_seconds,
        )

    def get_json(self, key: str) -> Any | None:
        value = self._client.get(self._key(key))
        if value is None:
            return None
        return json.loads(value)

    def acquire_lock(self, key: str, *, ttl_seconds: int) -> str | None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        token = str(uuid4())
        acquired = self._client.set(self._key(f"lock:{key}"), token, nx=True, ex=ttl_seconds)
        return token if acquired else None

    def release_lock(self, key: str, token: str) -> bool:
        released = self._client.eval(
            _RELEASE_LOCK_SCRIPT,
            1,
            self._key(f"lock:{key}"),
            token,
        )
        return bool(released)

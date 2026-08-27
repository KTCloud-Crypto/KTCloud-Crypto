import json

import pytest

from app.core.redis_store import RedisStore


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def ping(self):
        return True

    def set(self, key, value, *, ex, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def get(self, key):
        return self.values.get(key)

    def eval(self, script, key_count, key, token):
        if self.values.get(key) != token:
            return 0
        del self.values[key]
        return 1


def test_redis_json_cache_round_trip() -> None:
    store = RedisStore(FakeRedis())

    store.set_json("price:KRW-BTC", {"price": 100_000_000}, ttl_seconds=5)

    assert store.ping() is True
    assert store.get_json("price:KRW-BTC") == {"price": 100_000_000}


def test_redis_lock_requires_owner_token_to_release() -> None:
    store = RedisStore(FakeRedis())

    token = store.acquire_lock("order:10", ttl_seconds=10)

    assert token is not None
    assert store.acquire_lock("order:10", ttl_seconds=10) is None
    assert store.release_lock("order:10", "not-the-owner") is False
    assert store.release_lock("order:10", token) is True


def test_redis_cache_requires_positive_ttl() -> None:
    store = RedisStore(FakeRedis())

    with pytest.raises(ValueError):
        store.set_json("price:KRW-BTC", json.loads("{}"), ttl_seconds=0)

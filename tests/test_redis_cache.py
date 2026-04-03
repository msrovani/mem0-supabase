import types
from typing import List, Any, Optional

import pytest

from mem0-supabasee.mem0-supabase.mem0.cache import RedisSemanticCache, HybridCache  # type: ignore


class MockRedisHit:
    def __init__(self):
        self.commands = []
        self.vsim_hit = True
        self.vsim_score = 0.97
        self.item_id = "item1"
        self.responses = {("semantic_cache:vectors", self.item_id, "response_text"): "cached response"}

    def ping(self):
        return True

    def execute_command(self, command, *args):
        self.commands.append((command, args))
        if command == "VSIM":
            if self.vsim_hit:
                return (self.vsim_score, self.item_id)
            return None
        if command == "VGETATTR":
            key, item_id, attr = args
            return self.responses.get((key, item_id, attr))
        if command in ("VADD", "VSETATTR", "EXPIRE"):
            return True
        if command == "PING":
            return True
        return None


class MockL2:
    def __init__(self):
        self.calls = []
    def get(self, embedding: List[float], threshold: float):
        self.calls.append(("get", embedding, threshold))
        return "L2 response"
    def set(self, *args, **kwargs):
        self.calls.append(("set", args, kwargs))


class BrokenRedis(MockRedisHit):
    def __init__(self):
        super().__init__()
    def execute_command(self, command, *args):
        raise RuntimeError("unavailable")


def test_redis_cache_hit():
    mock = MockRedisHit()
    cache = RedisSemanticCache(redis_client=mock)
    result = cache.get([0.1, 0.2, 0.3], threshold=0.9)
    assert result == "cached response"
    # VSIM should have been called
    assert any(cmd == "VSIM" for cmd, _ in mock.commands)
    # VGETATTR should have been called
    assert any(cmd == "VGETATTR" for cmd, _ in mock.commands)


def test_redis_cache_miss_fallback_to_l2_and_populate():
    mock = MockRedisHit()
    mock.vsim_hit = False
    cache = RedisSemanticCache(redis_client=mock)
    l2 = MockL2()
    hybrid = HybridCache(enable_redis_cache=True, l2_client=l2, ttl_seconds=3600, redis_config=types.SimpleNamespace(redis_url=None))
    # Inject the mock redis as the Redis implementation inside HybridCache
    hybrid.redis_cache = mock
    res = hybrid.get([0.1, 0.2, 0.3], threshold=0.9)
    assert res == "L2 response"
    # L2 was used
    assert l2.calls and l2.calls[0][0] == "get"
-    # L1 should have been populated
    assert any(cmd in ("VADD", "VSETATTR") for cmd, _ in mock.commands)


def test_redis_unavailable_falls_back_to_l2():
    mock = BrokenRedis()
    cache = RedisSemanticCache(redis_client=mock)
    l2 = MockL2()
    hybrid = HybridCache(enable_redis_cache=True, l2_client=l2, ttl_seconds=3600, redis_config=types.SimpleNamespace(redis_url=None))
    hybrid.redis_cache = mock
    res = hybrid.get([0.1, 0.2, 0.3], threshold=0.9)
    assert res == "L2 response"

"""
Query Plan Cache — LRU cache for frequent filter combinations.

Caches results of common query patterns with TTL-based expiration
to reduce database load for repeated searches.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

__all__ = ["QueryPlanCache"]


class _CacheEntry:
    """Single cache entry with TTL and hit tracking."""

    __slots__ = ("result", "expires_at", "hits", "created_at")

    def __init__(self, result: Any, ttl: float):
        self.result = result
        self.expires_at = time.monotonic() + ttl
        self.hits = 0
        self.created_at = time.monotonic()


class QueryPlanCache:
    """
    LRU cache for query plans (filter combinations) with TTL.

    Usage:
        cache = QueryPlanCache(ttl_seconds=300, max_entries=1000)
        result = cache.get(filters={"user_id": "u1"}, limit=10)
        if result is None:
            result = vector_store.search(...)
            cache.set(filters={"user_id": "u1"}, limit=10, result=result)
        print(cache.get_stats())
    """

    def __init__(self, ttl_seconds: float = 300.0, max_entries: int = 1000):
        """
        Initialize QueryPlanCache.

        Args:
            ttl_seconds: Time-to-live for cache entries (default 300s).
            max_entries: Maximum cache size before LRU eviction (default 1000).
        """
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._store: OrderedDict[str, _CacheEntry] = OrderedDict()

        # Stats
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, filters: Optional[Dict[str, Any]], limit: int, user_id: Optional[str] = None) -> Optional[Any]:
        """
        Get cached result for a query plan.

        Args:
            filters: Query filters dict.
            limit: Result limit.
            user_id: Optional user identifier.

        Returns:
            Cached result, or None on miss/expiry.
        """
        key = self._make_key(filters, limit, user_id)

        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None

            if time.monotonic() > entry.expires_at:
                # Expired
                del self._store[key]
                self._misses += 1
                return None

            # Hit
            entry.hits += 1
            self._hits += 1
            self._store.move_to_end(key)
            return entry.result

    def set(self, filters: Optional[Dict[str, Any]], limit: int, user_id: Optional[str], result: Any) -> None:
        """
        Cache a query plan result.

        Args:
            filters: Query filters dict.
            limit: Result limit.
            user_id: Optional user identifier.
            result: The result to cache.
        """
        key = self._make_key(filters, limit, user_id)

        with self._lock:
            # Evict expired entries
            self._evict_expired()

            # Evict oldest if at capacity
            while len(self._store) >= self._max_entries:
                self._store.popitem(last=False)
                self._evictions += 1

            self._store[key] = _CacheEntry(result, self._ttl)
            self._store.move_to_end(key)

    def invalidate(self, filters: Optional[Dict[str, Any]] = None, user_id: Optional[str] = None) -> None:
        """
        Invalidate cache entries.

        Args:
            filters: If provided, invalidate all entries matching these filters.
                If None, invalidate all entries for the given user_id.
            user_id: If provided with filters, only invalidate matching entries.
                If provided without filters, invalidate all entries for this user.
        """
        with self._lock:
            if filters is None and user_id is None:
                # Clear all
                count = len(self._store)
                self._store.clear()
                logger.debug(f"QueryPlanCache: invalidated all {count} entries")
                return

            keys_to_remove = []
            for key, entry in self._store.items():
                if user_id and user_id not in key:
                    continue
                if filters:
                    # Check if filters are a subset of the cached key's filters
                    key_filters_str = key.split("|")[0]
                    filters_str = json.dumps(filters, sort_keys=True)
                    if key_filters_str == filters_str:
                        keys_to_remove.append(key)
                else:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._store[key]

            if keys_to_remove:
                logger.debug(f"QueryPlanCache: invalidated {len(keys_to_remove)} entries")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache performance statistics.

        Returns:
            Dict with hit_rate, miss_rate, size, evictions, ttl_seconds.
        """
        with self._lock:
            total = self._hits + self._misses
            return {
                "hit_rate": round(self._hits / max(total, 1), 4),
                "miss_rate": round(self._misses / max(total, 1), 4),
                "size": len(self._store),
                "max_entries": self._max_entries,
                "evictions": self._evictions,
                "hits": self._hits,
                "misses": self._misses,
                "ttl_seconds": self._ttl,
            }

    def _make_key(self, filters: Optional[Dict[str, Any]], limit: int, user_id: Optional[str]) -> str:
        """Create a deterministic cache key from query parameters."""
        filters_str = json.dumps(filters or {}, sort_keys=True)
        raw = f"{filters_str}|{limit}|{user_id or ''}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _evict_expired(self) -> None:
        """Remove expired entries (must be called with lock held)."""
        now = time.monotonic()
        expired = [k for k, v in self._store.items() if now > v.expires_at]
        for k in expired:
            del self._store[k]
        if expired:
            logger.debug(f"QueryPlanCache: evicted {len(expired)} expired entries")

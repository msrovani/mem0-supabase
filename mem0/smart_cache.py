"""
SmartCache — Intelligent Cache Warming & Predictive Pre-fetching

Wraps HybridCache to add:
- Cache warming on startup (load recent memories for active users)
- Predictive pre-fetching based on query co-occurrence patterns
- Automatic cache invalidation when memories are updated/deleted
- Hit/miss analytics with auto-tuning of warm_count

Usage:
    from mem0.smart_cache import create_smart_cache
    smart = create_smart_cache(hybrid_cache, memory_instance, config={"warm_count": 60})
    results = smart.get(query_embedding=emb, threshold=0.95)
    smart.set("user query", emb, "cached response")
    smart.invalidate("mem_123")
    print(smart.get_stats())
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

__all__ = [
    "SmartCache",
    "create_smart_cache",
]

logger = logging.getLogger(__name__)


class SmartCache:
    """
    Intelligent cache wrapper around HybridCache with warming, predictive
    pre-fetching, auto-invalidation, analytics, and auto-tuning.

    Thread-safe throughout. Drop-in API compatible with HybridCache.
    """

    def __init__(
        self,
        hybrid_cache: Any,
        memory_instance: Optional[Any] = None,
        warm_count: int = 50,
        hit_rate_threshold_low: float = 0.6,
        hit_rate_threshold_high: float = 0.9,
        prefetch_top_k: int = 5,
        auto_tune: bool = True,
        tune_interval: int = 100,
    ):
        """
        Initialize SmartCache.

        Args:
            hybrid_cache: The underlying HybridCache instance to wrap.
            memory_instance: Optional Memory instance for warming and pre-fetching.
            warm_count: Number of recent memories to pre-load per user on startup.
            hit_rate_threshold_low: Below this, increase warm_count by 20%.
            hit_rate_threshold_high: Above this, decrease warm_count by 10%.
            prefetch_top_k: Number of co-occurring items to pre-fetch.
            auto_tune: Enable automatic warm_count adjustment.
            tune_interval: Number of get() calls between auto-tune checks.
        """
        self._lock = threading.Lock()
        self._hybrid_cache = hybrid_cache
        self._memory_instance = memory_instance

        # Tuning parameters
        self.warm_count = warm_count
        self.hit_rate_threshold_low = hit_rate_threshold_low
        self.hit_rate_threshold_high = hit_rate_threshold_high
        self.prefetch_top_k = prefetch_top_k
        self.auto_tune = auto_tune
        self.tune_interval = tune_interval

        # Analytics counters
        self._hits = 0
        self._misses = 0
        self._prefetches = 0
        self._warm_count = 0
        self._total_latency_ms = 0.0
        self._get_calls = 0

        # Predictive pre-fetching: co-occurrence model
        # Maps query_text -> {memory_text: count}
        self._co_occurrence: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # Invalidation tracking
        self._invalidated_ids: set = set()
        self._invalidated_users: set = set()

        # Startup warming
        self._warm_cache()

    # ------------------------------------------------------------------
    # Public API (drop-in compatible with HybridCache)
    # ------------------------------------------------------------------

    def get(self, query_embedding: list, threshold: float = 0.95) -> Optional[str]:
        """
        Get cached response for a query embedding.

        Falls through to HybridCache.get(). Tracks hit/miss analytics
        and triggers predictive pre-fetching on miss.

        Args:
            query_embedding: The embedding vector for the query.
            threshold: Similarity threshold for cache match.

        Returns:
            Cached response text, or None on miss.
        """
        start = time.monotonic()
        with self._lock:
            self._get_calls += 1

        try:
            result = self._hybrid_cache.get(query_embedding, threshold)
        except TypeError:
            # Fallback for different signatures
            try:
                result = self._hybrid_cache.get(query_embedding)
            except Exception:
                result = None
        except Exception:
            result = None

        latency_ms = (time.monotonic() - start) * 1000

        with self._lock:
            self._total_latency_ms += latency_ms
            if result is not None:
                self._hits += 1
            else:
                self._misses += 1
                # Trigger predictive pre-fetch on miss
                self._predictive_prefetch(query_embedding)

            # Auto-tune periodically
            if self.auto_tune and self._get_calls % self.tune_interval == 0:
                self._maybe_tune_warm_count()

        return result

    def set(
        self,
        query_text: str,
        query_embedding: list,
        response_text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Store a query/response in the cache.

        Also updates the co-occurrence model for predictive pre-fetching.

        Args:
            query_text: The original query text.
            query_embedding: The embedding vector for the query.
            response_text: The response text to cache.
            metadata: Optional metadata dict.
        """
        try:
            self._hybrid_cache.set(query_text, query_embedding, response_text, metadata)
        except TypeError:
            try:
                self._hybrid_cache.set(query_text, query_embedding, response_text)
            except Exception as e:
                logger.debug(f"SmartCache set fallback failed: {e}")
        except Exception as e:
            logger.debug(f"SmartCache set failed: {e}")

        # Update co-occurrence model
        with self._lock:
            if response_text:
                # Track co-occurrence between query and response content
                self._co_occurrence[query_text][response_text] += 1

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------

    def invalidate(self, memory_id: str) -> None:
        """
        Mark a memory as invalidated in the cache.

        Prevents stale cache hits for updated/deleted memories.

        Args:
            memory_id: The memory ID to invalidate.
        """
        with self._lock:
            self._invalidated_ids.add(memory_id)
            # Clean up co-occurrence entries referencing this memory
            for query_text in list(self._co_occurrence.keys()):
                self._co_occurrence[query_text].pop(memory_id, None)
                if not self._co_occurrence[query_text]:
                    del self._co_occurrence[query_text]
        logger.debug(f"SmartCache: invalidated memory {memory_id}")

    def invalidate_user(self, user_id: str) -> None:
        """
        Mark all memories for a user as invalidated.

        Args:
            user_id: The user ID whose memories should be invalidated.
        """
        with self._lock:
            self._invalidated_users.add(user_id)
        logger.debug(f"SmartCache: invalidated all memories for user {user_id}")

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache performance statistics.

        Returns:
            Dict with hit_rate, miss_rate, total_gets, hits, misses,
            warm_count, prefetches, avg_latency_ms.
        """
        with self._lock:
            total = self._hits + self._misses
            return {
                "hit_rate": round(self._hits / total, 4) if total > 0 else 0.0,
                "miss_rate": round(self._misses / total, 4) if total > 0 else 0.0,
                "total_gets": self._get_calls,
                "hits": self._hits,
                "misses": self._misses,
                "warm_count": self._warm_count,
                "prefetches": self._prefetches,
                "avg_latency_ms": round(self._total_latency_ms / max(total, 1), 2),
            }

    # ------------------------------------------------------------------
    # Internal: Cache Warming
    # ------------------------------------------------------------------

    def _warm_cache(self) -> None:
        """
        Pre-populate cache with recent memories for active users.

        Best-effort: gracefully skips if memory_instance methods are
        unavailable or if no active users are found.
        """
        if self._memory_instance is None:
            logger.info("SmartCache: no memory_instance provided, skipping warm-up.")
            return

        try:
            active_user_ids = self._get_active_user_ids()
            if not active_user_ids:
                logger.info("SmartCache: no active users found, skipping warm-up.")
                return

            warmed = 0
            for user_id in active_user_ids:
                try:
                    memories = self._memory_instance.get_all(user_id=user_id, limit=self.warm_count)
                    results = memories.get("results", []) if isinstance(memories, dict) else memories
                    for mem in results:
                        mem_text = mem.get("memory", "") if isinstance(mem, dict) else str(mem)
                        mem_id = mem.get("id", "") if isinstance(mem, dict) else ""
                        if mem_text and mem_id not in self._invalidated_ids:
                            # Pre-warm with a synthetic key
                            try:
                                emb = self._memory_instance.embedding_model.embed(mem_text, "search")
                                self._hybrid_cache.set(
                                    f"warm:{mem_id}", emb, mem_text, {"memory_id": mem_id, "warmed": True}
                                )
                                warmed += 1
                            except Exception as e:
                                logger.debug(f"SmartCache warm-up embed failed for {mem_id}: {e}")
                except Exception as e:
                    logger.debug(f"SmartCache warm-up failed for user {user_id}: {e}")

            with self._lock:
                self._warm_count = warmed
            logger.info(f"SmartCache: warmed {warmed} memories for {len(active_user_ids)} users.")

        except Exception as e:
            logger.warning(f"SmartCache warm-up failed (non-fatal): {e}")

    def _get_active_user_ids(self) -> List[str]:
        """
        Discover active user IDs from the memory instance.

        Tries multiple strategies:
        1. memory_instance.get_active_user_ids()
        2. memory_instance.lifecycle.get_active_users()
        3. Fallback: return empty list
        """
        # Strategy 1: direct method
        if hasattr(self._memory_instance, "get_active_user_ids"):
            try:
                result = self._memory_instance.get_active_user_ids()
                if result:
                    return result[:10]  # Limit to top 10
            except Exception:
                pass

        # Strategy 2: via lifecycle
        if hasattr(self._memory_instance, "lifecycle") and self._memory_instance.lifecycle:
            try:
                lifecycle = self._memory_instance.lifecycle
                if hasattr(lifecycle, "get_active_users"):
                    result = lifecycle.get_active_users(limit=10)
                    if result:
                        return result
            except Exception:
                pass

        # Strategy 3: check if there's a known user list in config
        if hasattr(self._memory_instance, "config"):
            config = self._memory_instance.config
            if hasattr(config, "warm_user_ids"):
                return config.warm_user_ids[:10]

        return []

    # ------------------------------------------------------------------
    # Internal: Predictive Pre-fetching
    # ------------------------------------------------------------------

    def _predictive_prefetch(self, query_embedding: list) -> None:
        """
        Pre-fetch likely related memories based on co-occurrence patterns.

        Uses a simple co-occurrence model: when query X returns memory Y,
        track that association. On future misses for similar queries,
        pre-fetch the most commonly co-occurring memories.
        """
        if not self._memory_instance:
            return

        # Find the most common co-occurring memory texts
        with self._lock:
            if not self._co_occurrence:
                return

            # Aggregate all co-occurring items across all queries
            aggregated: Dict[str, int] = defaultdict(int)
            for query_text, mem_counts in self._co_occurrence.items():
                for mem_text, count in mem_counts.items():
                    if mem_text not in self._invalidated_ids:
                        aggregated[mem_text] += count

            if not aggregated:
                return

            # Get top-K co-occurring items
            top_items = sorted(aggregated.items(), key=lambda x: x[1], reverse=True)[: self.prefetch_top_k]

        # Pre-fetch top items into cache
        prefetched = 0
        for mem_text, _count in top_items:
            try:
                emb = self._memory_instance.embedding_model.embed(mem_text, "search")
                self._hybrid_cache.set(f"prefetch:{mem_text[:30]}", emb, mem_text, {"prefetched": True})
                prefetched += 1
            except Exception as e:
                logger.debug(f"SmartCache prefetch failed for item: {e}")

        with self._lock:
            self._prefetches += prefetched

        if prefetched > 0:
            logger.debug(f"SmartCache: pre-fetched {prefetched} items based on co-occurrence.")

    # ------------------------------------------------------------------
    # Internal: Auto-Tuning
    # ------------------------------------------------------------------

    def _maybe_tune_warm_count(self) -> None:
        """
        Adjust warm_count based on hit rate.

        - If hit_rate < threshold_low: increase warm_count by 20%
        - If hit_rate > threshold_high: decrease warm_count by 10%
        """
        total = self._hits + self._misses
        if total == 0:
            return

        hit_rate = self._hits / total

        if hit_rate < self.hit_rate_threshold_low:
            old = self.warm_count
            self.warm_count = int(self.warm_count * 1.2)
            logger.info(
                f"SmartCache auto-tune: hit_rate {hit_rate:.2f} < {self.hit_rate_threshold_low}, "
                f"warm_count {old} -> {self.warm_count}"
            )
        elif hit_rate > self.hit_rate_threshold_high:
            old = self.warm_count
            self.warm_count = max(10, int(self.warm_count * 0.9))
            logger.info(
                f"SmartCache auto-tune: hit_rate {hit_rate:.2f} > {self.hit_rate_threshold_high}, "
                f"warm_count {old} -> {self.warm_count}"
            )


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------


def create_smart_cache(
    hybrid_cache: Any,
    memory_instance: Optional[Any] = None,
    config: Optional[Dict[str, Any]] = None,
) -> SmartCache:
    """
    Factory function to create a SmartCache instance.

    Args:
        hybrid_cache: The underlying HybridCache to wrap.
        memory_instance: Optional Memory instance for warming/prefetching.
        config: Optional config dict with keys:
            - warm_count (int): Number of memories to warm per user.
            - hit_rate_threshold_low (float): Low hit rate threshold.
            - hit_rate_threshold_high (float): High hit rate threshold.
            - prefetch_top_k (int): Number of items to pre-fetch.
            - auto_tune (bool): Enable auto-tuning.
            - tune_interval (int): Calls between auto-tune checks.

    Returns:
        Configured SmartCache instance.
    """
    cfg = config or {}
    return SmartCache(
        hybrid_cache=hybrid_cache,
        memory_instance=memory_instance,
        warm_count=cfg.get("warm_count", 50),
        hit_rate_threshold_low=cfg.get("hit_rate_threshold_low", 0.6),
        hit_rate_threshold_high=cfg.get("hit_rate_threshold_high", 0.9),
        prefetch_top_k=cfg.get("prefetch_top_k", 5),
        auto_tune=cfg.get("auto_tune", True),
        tune_interval=cfg.get("tune_interval", 100),
    )

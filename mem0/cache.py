import os
import logging
from typing import Optional, Dict, Any
from supabase import create_client, Client

# Optional Redis integration for L1 cache
try:
    from .cache_redis import RedisSemanticCache  # type: ignore
except Exception:
    RedisSemanticCache = None  # type: ignore

logger = logging.getLogger(__name__)


class SemanticCache:
    """
    Semantic Cache implementation using Supabase and pgvector.
    Saves LLM costs by returning cached responses for semantically similar queries.
    """

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        url = url or os.environ.get("SUPABASE_URL")
        key = key or os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")

        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY/SERVICE_KEY are required for SemanticCache.")

        self.client: Client = create_client(url, key)

    def get(self, query_embedding: list, threshold: float = 0.95) -> Optional[str]:
        """
        Check if a similar query exists in the cache.
        """
        try:
            rpc_params = {"query_embedding": query_embedding, "match_threshold": threshold, "match_count": 1}
            response = self.client.rpc("match_semantic_cache", rpc_params).execute()

            if response.data and len(response.data) > 0:
                logger.info(f"Semantic Cache Hit! Similarity: {response.data[0].get('similarity')}")
                return response.data[0].get("response_text")

            return None
        except Exception as e:
            logger.error(f"Error querying semantic cache: {e}")
            return None

    def set(
        self, query_text: str, query_embedding: list, response_text: str, metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Store a new query and response in the cache.
        """
        try:
            data = {
                "query_text": query_text,
                "embedding": query_embedding,
                "response_text": response_text,
                "metadata": metadata or {},
            }
            self.client.table("semantic_cache").insert(data).execute()
        except Exception as e:
            logger.error(f"Error saving to semantic cache: {e}")


class HybridCache:
    """Hybrid L1/L2 cache: Redis (L1) + Supabase (L2).

    - L1: RedisCache if enabled, fast (<10ms)
    - L2: Supabase-based SemanticCache (existing implementation)
    - On L1 miss, fetch from L2 and populate L1
    - TTL for L1 entries supports eviction through Redis EXPIRE
    - Backward compatible with existing SemanticCache API for L2 operations
    """

    def __init__(
        self,
        redis_config: Optional[Any] = None,
        enable_redis_cache: bool = False,
        l2_client: Optional[SemanticCache] = None,
        ttl_seconds: int = 3600,
        redis_client: Optional[Any] = None,
    ):
        # Initialize L2 (Supabase) cache
        self.l2_cache: SemanticCache = l2_client if l2_client is not None else SemanticCache()
        self.enable_redis_cache = enable_redis_cache
        self.ttl_seconds = ttl_seconds
        self.redis_cache: Optional[Any] = None
        if self.enable_redis_cache:
            try:
                self.redis_cache = (
                    RedisSemanticCache(
                        redis_url=getattr(redis_config, "redis_url", None),
                        ttl_seconds=self.ttl_seconds,
                        quantization=getattr(redis_config, "redis_quantization", "Q8"),
                        redis_client=redis_client,
                    )
                    if RedisSemanticCache is not None
                    else None
                )
            except Exception as e:
                logger.warning(f"Redis cache init failed, falling back to L2: {e}")
                self.redis_cache = None
                self.enable_redis_cache = False

    def get(self, query_embedding: list, threshold: float = 0.95) -> Optional[str]:
        # Try L1 first
        if self.redis_cache is not None:
            try:
                res = self.redis_cache.get(query_embedding, threshold)
                if res is not None:
                    return res
            except Exception as e:
                # On Redis issues, fall back to L2
                logger.warning(f"Redis L1 cache miss due to error, falling back to L2: {e}")
                pass
        # Fall back to L2
        res = self.l2_cache.get(query_embedding, threshold)
        if res is not None and self.redis_cache is not None:
            # Populate L1
            try:
                query_text = str(hash(tuple(query_embedding)))
                self.redis_cache.set(
                    query_text=query_text, query_embedding=query_embedding, response_text=res, metadata=None
                )
            except Exception as e:
                logger.debug(f"Failed to populate Redis L1 cache: {e}")
                pass
        return res

    def set(
        self, query_text: str, query_embedding: list, response_text: str, metadata: Optional[Dict[str, Any]] = None
    ):
        # Persist to L2
        self.l2_cache.set(query_text, query_embedding, response_text, metadata)
        # Persist to L1 if enabled
        if self.redis_cache is not None:
            try:
                self.redis_cache.set(query_text, query_embedding, response_text, metadata)
            except Exception as e:
                logger.debug(f"Failed to persist to Redis L1 cache: {e}")
                pass

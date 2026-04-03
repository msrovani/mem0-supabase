"""Redis-backed semantic cache using Vector Sets (Redis 8.0).

This module provides RedisSemanticCache which stores embeddings in a Redis Vector Set
and associated metadata using VSETATTR. It supports configurable quantization and a
graceful fallback when Redis is unavailable.
"""

from __future__ import annotations

import json
import hashlib
import logging
from typing import List, Optional, Any

logger = logging.getLogger(__name__)


class RedisSemanticCache:
    """A lightweight Redis-backed semantic cache using Vector Sets (VADD/VSIM).

    This class is designed to be used as an optional L1 cache. On initialization, it
    can accept an injected redis client for testing or fall back to a real Redis
    client created from a Redis URL. The actual Redis integration relies on the
    vector-sets commands available in Redis 8.0+.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        quantization: str = "Q8",
        ttl_seconds: Optional[int] = None,
        redis_client: Optional[Any] = None,
        fallback_on_error: bool = True,
    ):
        self.redis_url = redis_url
        self.quantization = quantization
        self.ttl_seconds = ttl_seconds
        self._client = redis_client  # type: ignore
        self.enabled = False
        if self._client is not None:
            self.enabled = True
        else:
            try:
                from redis import Redis  # lazy import

                # Import inside to avoid hard dependency if not used
                self._client = Redis.from_url(redis_url or "redis://localhost:6379")
                self.enabled = True
            except Exception:
                # Graceful degradation if redis is unavailable
                self.enabled = False
        # Use a stable vector set key; allow override if needed later
        self._vs_key = "semantic_cache:vectors"  # vector set key
        self._fallback_on_error = fallback_on_error

    # Internal helpers
    def _ensure_client(self) -> bool:
        if self._client is None:
            return False
        try:
            # Ping to ensure health if possible
            if hasattr(self._client, "ping"):
                self._client.ping()
            return True
        except Exception:
            return False

    def get(
        self, query_embedding: List[float], threshold: float = 0.95
    ) -> Optional[str]:
        """Retrieve a cached response text if a similar embedding exists in Redis.

        Returns the cached response text or None if not found or on error.
        """
        if not self.enabled or not self._ensure_client():
            return None
        try:
            # Vector similarity search via VSIM. Expecting a tuple/list like: [score, id]
            res = self._client.execute_command(
                "VSIM", self._vs_key, *query_embedding, "LIMIT", 1
            )
            if not res:
                logger.info("Redis L1 miss (no VSIM result)")
                return None
            # Normalize the result depending on how redis-py returns it
            score = None
            item_id = None
            if isinstance(res, (list, tuple)) and len(res) >= 2:
                score, item_id = res[0], res[1]
            elif isinstance(res, (list, tuple)) and len(res) == 1:
                item_id = res[0]
            else:
                # Fallback: assume first element is score and second is id if present
                try:
                    score = res[0]  # type: ignore
                    item_id = res[1]  # type: ignore
                except Exception:
                    item_id = None
            if item_id is None:
                logger.info("Redis L1 miss (no item_id from VSIM)")
                return None
            if score is not None and score < threshold:
                logger.info(
                    f"Redis L1 similarity below threshold: {score} < {threshold}"
                )
                return None
            # Retrieve the cached response_text attribute for the item
            resp = self._client.execute_command(
                "VGETATTR", self._vs_key, item_id, "response_text"
            )
            if isinstance(resp, (bytes, str)):
                return resp.decode() if isinstance(resp, bytes) else resp
            return resp
        except Exception as e:
            logger.error(f"Redis L1 get failed: {e}")
            if self._fallback_on_error:
                return None
            raise

    def set(
        self,
        query_text: str,
        query_embedding: List[float],
        response_text: str,
        metadata: Optional[dict] = None,
    ):
        """Store a query/response pair in Redis Vector Set with optional metadata."""
        if not self.enabled or not self._ensure_client():
            return
        try:
            # Deterministic id for the embedding to avoid collisions
            item_id = hashlib.sha256((query_text or "").encode("utf-8")).hexdigest()
            # Add the vector with its id
            self._client.execute_command(
                "VADD", self._vs_key, item_id, *query_embedding
            )
            # Attach attributes for retrieval
            self._client.execute_command(
                "VSETATTR", self._vs_key, item_id, "response_text", response_text
            )
            if metadata:
                self._client.execute_command(
                    "VSETATTR", self._vs_key, item_id, "metadata", json.dumps(metadata)
                )
            # Optional quantization metadata
            if self.quantization:
                self._client.execute_command(
                    "VSETATTR", self._vs_key, item_id, "quantization", self.quantization
                )
            if self.ttl_seconds and self.ttl_seconds > 0:
                # Apply TTL to the vector set as a whole for simplicity
                self._client.execute_command(
                    "EXPIRE", self._vs_key, int(self.ttl_seconds)
                )
        except Exception as e:
            logger.error(f"Redis L1 set failed: {e}")
            if self._fallback_on_error:
                return
            raise

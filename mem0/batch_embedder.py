"""
Batch Embedder — Groups multiple texts into efficient batch operations.

Wraps any embedder to support batched embeddings, reducing LLM API calls
by up to 32x when processing multiple texts.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = ["BatchEmbedder"]


class BatchEmbedder:
    """
    Batch-capable embedder wrapper with concurrent fallback.

    Usage:
        embedder = OpenAIEmbedder(...)
        batch = BatchEmbedder(embedder, batch_size=32)
        vectors = batch.embed(["text1", "text2", ...], mode="search")
        print(batch.get_stats())
    """

    def __init__(self, embedder: Any, batch_size: int = 32, max_workers: int = 8):
        """
        Initialize BatchEmbedder.

        Args:
            embedder: An object with embed(text, mode) -> List[float].
                If it also has embed_batch(texts, mode) -> List[List[float]],
                batch mode is used automatically.
            batch_size: Number of texts per batch when using embed_batch.
            max_workers: Max threads for concurrent individual embed() calls.
        """
        self.embedder = embedder
        self.batch_size = batch_size
        self.max_workers = max_workers
        self._has_batch = hasattr(embedder, "embed_batch")
        self._lock = threading.Lock()

        # Stats
        self._total_texts = 0
        self._batch_calls = 0
        self._individual_calls = 0
        self._total_latency_ms = 0.0

    def embed(self, texts, mode: str = "search") -> List[List[float]]:
        """
        Embed one or more texts, using batch or concurrent fallback.

        Args:
            texts: A single string or list of strings.
            mode: Embedding mode ("search", "add", "update").

        Returns:
            List of embedding vectors (one per input text).
        """
        if isinstance(texts, str):
            texts = [texts]

        if not texts:
            return []

        start = time.monotonic()

        if self._has_batch:
            result = self._embed_batch(texts, mode)
        else:
            result = self._embed_concurrent(texts, mode)

        latency_ms = (time.monotonic() - start) * 1000

        with self._lock:
            self._total_texts += len(texts)
            self._total_latency_ms += latency_ms

        return result

    def _embed_batch(self, texts: List[str], mode: str) -> List[List[float]]:
        """Embed using batch API with chunking."""
        all_results: List[List[float]] = []

        for i in range(0, len(texts), self.batch_size):
            chunk = texts[i : i + self.batch_size]
            try:
                results = self.embedder.embed_batch(chunk, mode)
                all_results.extend(results)
                with self._lock:
                    self._batch_calls += 1
            except Exception as e:
                logger.warning(f"Batch embed failed, falling back to individual: {e}")
                # Fallback to individual
                for text in chunk:
                    try:
                        all_results.append(self.embedder.embed(text, mode))
                    except Exception as e2:
                        logger.error(f"Individual embed failed: {e2}")
                        all_results.append([0.0] * 1536)
                with self._lock:
                    self._individual_calls += len(chunk)

        return all_results

    def _embed_concurrent(self, texts: List[str], mode: str) -> List[List[float]]:
        """Embed using ThreadPoolExecutor for parallel individual calls."""
        results: Dict[int, List[float]] = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.embedder.embed, text, mode): i for i, text in enumerate(texts)}

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.error(f"Concurrent embed failed for text {idx}: {e}")
                    results[idx] = [0.0] * 1536

        with self._lock:
            self._individual_calls += len(texts)

        # Return in original order
        return [results[i] for i in range(len(texts))]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get embedding performance statistics.

        Returns:
            Dict with total_texts, batch_calls, individual_calls,
            total_latency_ms, avg_latency_per_text, batch_usage_rate.
        """
        with self._lock:
            total = self._total_texts
            latency = self._total_latency_ms
            batch = self._batch_calls
            individual = self._individual_calls

        return {
            "total_texts": total,
            "batch_calls": batch,
            "individual_calls": individual,
            "total_latency_ms": round(latency, 2),
            "avg_latency_per_text_ms": round(latency / max(total, 1), 4),
            "batch_usage_rate": round(batch / max(batch + individual, 1), 4),
        }

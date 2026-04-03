"""
LlamaIndex Integration — Mem0VectorStore for LlamaIndex.

Usage:
    from mem0.llamaindex_integration import Mem0VectorStore

    store = Mem0VectorStore(
        base_url="http://localhost:8000",
        user_id="user1",
        api_key="your-jwt-token",
    )

    index = VectorStoreIndex.from_vector_store(store)
    query_engine = index.as_query_engine()
    response = query_engine.query("What do I know about pizza?")
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = ["Mem0VectorStore"]


class Mem0VectorStore:
    """
    LlamaIndex-compatible vector store backed by Mem0.

    Enables LlamaIndex to use Mem0's cognitive memory system
    as a retrieval backend.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.user_id = user_id
        self.agent_id = agent_id
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            from mem0.client import Mem0Client
            self._client = Mem0Client(base_url=self.base_url, api_key=self.api_key)
        return self._client

    @property
    def client(self):
        return self._get_client()

    @property
    def stores_text(self) -> bool:
        return True

    @property
    def is_embedding_query(self) -> bool:
        return True

    def add(self, nodes: List[Any], **add_kwargs: Any) -> List[str]:
        """
        Add nodes to Mem0.

        Args:
            nodes: List of LlamaIndex TextNode objects.

        Returns:
            List of memory IDs.
        """
        ids = []
        for node in nodes:
            try:
                result = self.client.add(
                    node.get_content(),
                    user_id=self.user_id,
                    agent_id=self.agent_id,
                    metadata={"node_id": node.node_id, **node.metadata} if node.metadata else None,
                )
                if result.get("results"):
                    ids.extend(r.get("id", "") for r in result["results"])
            except Exception as e:
                logger.warning(f"Failed to add node to Mem0: {e}")
        return ids

    def delete(self, ref_doc_id: str, **delete_kwargs: Any) -> None:
        """Delete a document from Mem0."""
        try:
            # Search for memories associated with this document
            results = self.client.search(ref_doc_id, user_id=self.user_id, agent_id=self.agent_id)
            for item in results.get("results", []):
                memory_id = item.get("id") or item.get("memory_id")
                if memory_id:
                    self.client.delete(memory_id)
        except Exception as e:
            logger.warning(f"Failed to delete from Mem0: {e}")

    def query(self, query: Any, **kwargs: Any) -> List[Any]:
        """
        Query Mem0 for relevant memories.

        Args:
            query: LlamaIndex VectorStoreQuery object.

        Returns:
            VectorStoreQueryResult with nodes and similarities.
        """
        try:
            results = self.client.search(
                query.query_str,
                user_id=self.user_id,
                agent_id=self.agent_id,
            )

            nodes = []
            similarities = []
            ids = []

            for item in results.get("results", []):
                from llama_index.core.schema import TextNode

                node = TextNode(
                    text=item.get("memory", ""),
                    id_=item.get("id") or item.get("memory_id", ""),
                    metadata={k: v for k, v in item.items() if k not in ("memory", "id", "memory_id")},
                )
                nodes.append(node)
                similarities.append(item.get("recollection_score") or item.get("score", 0.5))
                ids.append(item.get("id") or item.get("memory_id", ""))

            # Lazy import to avoid hard dependency
            from llama_index.core.vector_stores.types import VectorStoreQueryResult
            return VectorStoreQueryResult(nodes=nodes, similarities=similarities, ids=ids)

        except Exception as e:
            logger.warning(f"Failed to query Mem0: {e}")
            from llama_index.core.vector_stores.types import VectorStoreQueryResult
            return VectorStoreQueryResult(nodes=[], similarities=[], ids=[])

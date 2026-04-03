"""
Abstract Base Class Interfaces for mem0-supabase core services.

Enables dependency injection, mock testing, and provider hot-swapping.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = [
    "MemoryItem",
    "IVectorStore",
    "IGraphStore",
    "ILLM",
    "IEmbedder",
    "IReranker",
]


@dataclass(slots=True)
class MemoryItem:
    """Standardized memory item returned by vector store lookups."""

    id: str
    vector: Optional[List[float]] = None
    payload: Optional[Dict[str, Any]] = field(default_factory=dict)
    score: Optional[float] = None


class IVectorStore(ABC):
    """
    Abstract interface for vector store backends.

    Implementations: SupabaseVectorStore, QdrantVectorStore, etc.
    """

    @abstractmethod
    def insert(
        self,
        vectors: List[List[float]],
        ids: List[str],
        payloads: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        """Insert vectors with optional payloads. Returns inserted IDs."""

    @abstractmethod
    def get(self, vector_id: str) -> Optional[MemoryItem]:
        """Retrieve a single memory item by ID."""

    @abstractmethod
    def search(
        self,
        query: str,
        vectors: List[float],
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[MemoryItem]:
        """Search for similar vectors with optional filters."""

    @abstractmethod
    def update(
        self,
        vector_id: str,
        vector: List[float],
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update a vector and its payload."""

    @abstractmethod
    def delete(self, vector_id: str) -> None:
        """Delete a single vector by ID."""

    @abstractmethod
    def list(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> List[MemoryItem]:
        """List vectors matching filters."""

    @abstractmethod
    def delete_col(self) -> None:
        """Delete the entire collection."""

    # Default utility methods
    def _to_memory_item(self, data: Dict[str, Any]) -> MemoryItem:
        """Convert raw dict to MemoryItem."""
        return MemoryItem(
            id=data.get("id", ""),
            vector=data.get("vector"),
            payload=data.get("payload", {}),
            score=data.get("score"),
        )


class IGraphStore(ABC):
    """
    Abstract interface for graph store backends.

    Implementations: Neo4jGraph, MemgraphGraph, SupabaseGraph, etc.
    """

    @abstractmethod
    def add(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
    ) -> None:
        """Add nodes and edges to the graph."""

    @abstractmethod
    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search the graph for relevant nodes/edges."""

    @abstractmethod
    def get_all_nodes(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Retrieve all nodes matching filters."""

    @abstractmethod
    def get_all_edges(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Retrieve all edges matching filters."""

    @abstractmethod
    def delete_node(self, node_id: str) -> None:
        """Delete a node and its connected edges."""

    @abstractmethod
    def delete_edge(self, edge_id: str) -> None:
        """Delete an edge."""

    # Default utility methods
    def _clone_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Shallow clone a dict."""
        return dict(d)


class ILLM(ABC):
    """
    Abstract interface for language model providers.

    Implementations: OpenAILLM, AnthropicLLM, GroqLLLM, etc.
    """

    @abstractmethod
    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Generate a response from the LLM.

        Args:
            messages: List of {"role": str, "content": str} dicts.
            response_format: Optional {"type": "json_object"} for structured output.

        Returns:
            Generated response text.
        """

    @abstractmethod
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""

    # Default utility methods
    def _default_format(self, text: str) -> str:
        """Format text for display/logging."""
        return text[:200] + "..." if len(text) > 200 else text


class IEmbedder(ABC):
    """
    Abstract interface for embedding model providers.

    Implementations: OpenAIEmbedder, OllamaEmbedder, etc.
    """

    @abstractmethod
    def embed(self, text: str, mode: str = "search") -> List[float]:
        """
        Generate an embedding vector for the given text.

        Args:
            text: Input text to embed.
            mode: Usage mode ("add", "search", "update").

        Returns:
            Embedding vector as list of floats.
        """

    # Default utility methods
    def _normalize(self, vector: List[float]) -> List[float]:
        """L2-normalize a vector."""
        import math

        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            return vector
        return [v / norm for v in vector]


class IReranker(ABC):
    """
    Abstract interface for reranker providers.

    Implementations: ColbertReranker, CohereReranker, etc.
    """

    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents based on relevance to query.

        Args:
            query: Search query.
            documents: List of document dicts with at least "memory" or "text" key.
            limit: Maximum number of results to return.

        Returns:
            Reranked list of document dicts, each with a "score" key.
        """

    # Default utility methods
    def _limit_docs(self, documents: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        """Truncate document list to limit."""
        return documents[:limit]

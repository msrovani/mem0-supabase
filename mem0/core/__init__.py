"""Core interfaces for mem0-supabase: ABCs for dependency injection."""

from mem0.core.interfaces import IVectorStore, IGraphStore, ILLM, IEmbedder, IReranker, MemoryItem

__all__ = ["IVectorStore", "IGraphStore", "ILLM", "IEmbedder", "IReranker", "MemoryItem"]

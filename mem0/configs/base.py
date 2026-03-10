import os
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from mem0.embeddings.configs import EmbedderConfig
from mem0.llms.configs import LlmConfig
from mem0.vector_stores.configs import VectorStoreConfig
from mem0.graph_stores.configs import GraphStoreConfig
from mem0.reranker.configs import RerankerConfig


class AzureConfig(BaseModel):
    model_config = {"extra": "allow"}


# Set up the directory path
home_dir = os.path.expanduser("~")
mem0_dir = os.environ.get("MEM0_DIR") or os.path.join(home_dir, ".mem0")


class MemoryItem(BaseModel):
    id: str = Field(..., description="The unique identifier for the text data")
    memory: str = Field(
        ..., description="The memory deduced from the text data"
    )  # TODO After prompt changes from platform, update this
    hash: Optional[str] = Field(None, description="The hash of the memory")
    # The metadata value can be anything and not just string. Fix it
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for the text data")
    score: Optional[float] = Field(None, description="The score associated with the text data")
    created_at: Optional[str] = Field(None, description="The timestamp when the memory was created")
    updated_at: Optional[str] = Field(None, description="The timestamp when the memory was updated")


class MemoryConfig(BaseModel):
    vector_store: VectorStoreConfig = Field(
        description="Configuration for the vector store",
        default_factory=VectorStoreConfig,
    )
    llm: LlmConfig = Field(
        description="Configuration for the language model",
        default_factory=LlmConfig,
    )
    embedder: EmbedderConfig = Field(
        description="Configuration for the embedding model",
        default_factory=EmbedderConfig,
    )
    history_db_path: str = Field(
        description="Path to the history database",
        default=os.path.join(mem0_dir, "history.db"),
    )
    version: str = Field(
        description="The version of the API",
        default="v1.1",
    )
    custom_fact_extraction_prompt: Optional[str] = Field(
        description="Custom prompt for the fact extraction",
        default=None,
    )
    custom_update_memory_prompt: Optional[str] = Field(
        description="Custom prompt for the update memory",
        default=None,
    )
    graph_store: Optional[GraphStoreConfig] = Field(
        description="Configuration for the graph store",
        default=None,
    )
    reranker: Optional[RerankerConfig] = Field(
        description="Configuration for the reranker",
        default=None,
    )
    enable_resonance: bool = Field(
        description="Enable real-time synaptic resonance between agents (Supabase only)",
        default=False,
    )
    enable_ego: bool = Field(
        description="Enable Layer 12 Meta-Cognitive Identity (The Ego)",
        default=False,
    )
    enable_compression: bool = Field(
        description="Enable Semantic Compression (Intelligent Deduplication)",
        default=False,
    )
    compression_threshold: float = Field(
        description="Similarity above this triggers a semantic merge instead of a new entry",
        default=0.92,
    )
    enable_paging: bool = Field(
        description="Enable Context Orchestrator (Paging Mechanism)",
        default=False,
    )
    context_window_limit: int = Field(
        description="Limit of memories/tokens in active context before paging triggers",
        default=10,
    )
    enable_reflection: bool = Field(
        description="Enable Reflective Background Task (Self-Correction)",
        default=False,
    )
    reflection_interval: int = Field(
        description="Number of additions before triggering a reflection cycle",
        default=5,
    )
    enable_dreaming: bool = Field(
        description="Enable Dreaming Mode (Synthetic Memory Generation)",
        default=False,
    )
    dreaming_interval: int = Field(
        description="Number of additions before triggering a dreaming cycle",
        default=10,
    )
    enable_compaction: bool = Field(
        description="Enable Agentic Compaction (History Rewriting)",
        default=False,
    )
    enable_heartbeat: bool = Field(
        description="Enable Proactive Heartbeats (Autonomous Turns)",
        default=False,
    )
    heartbeat_interval: int = Field(
        description="Seconds between heartbeat checks",
        default=3600,
    )
    enable_bridge: bool = Field(
        description="Enable Memory Bridge (Multi-Agent Shared/Private)",
        default=False,
    )
    enable_tool_state: bool = Field(
        description="Enable Tool-State Memory (Save Game for tools)",
        default=False,
    )

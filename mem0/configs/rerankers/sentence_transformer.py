from typing import Optional
from pydantic import Field
from mem0.configs.rerankers.base import BaseRerankerConfig


class SentenceTransformerRerankerConfig(BaseRerankerConfig):
    model: str = Field(
        description="Model name for sentence transformer",
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
    )
    device: Optional[str] = Field(
        description="Device to use (e.g., 'cpu', 'cuda', 'mps')",
        default=None,
    )
    batch_size: int = Field(
        description="Batch size for reranking",
        default=32,
    )
    show_progress_bar: bool = Field(
        description="Whether to show progress bar during reranking",
        default=False,
    )

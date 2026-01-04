from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from mem0.configs.rerankers.base import BaseRerankerConfig

class RerankerConfig(BaseModel):
    provider: str = Field(
        description="Provider of the reranker (e.g. 'cohere')",
        default="cohere",
    )
    config: Optional[BaseRerankerConfig] = Field(
        description="Configuration for the specific reranker",
        default_factory=BaseRerankerConfig,
    )

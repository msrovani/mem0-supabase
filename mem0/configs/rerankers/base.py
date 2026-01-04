from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class BaseRerankerConfig(BaseModel):
    """
    Base configuration for rerankers.
    """
    model: Optional[str] = Field(None, description="The reranker model to use")
    top_k: int = Field(5, description="Number of results to return after reranking")
    api_key: Optional[str] = Field(None, description="API key for the reranker provider")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional configuration parameters")

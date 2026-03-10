from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class GraphStoreConfig(BaseModel):
    provider: str = Field(
        description="Provider of the graph store (e.g. 'supabase')",
        default="supabase",
    )
    config: Optional[Dict[str, Any]] = Field(
        description="Configuration for the specific graph store",
        default=None,
    )
    custom_prompt: Optional[str] = Field(
        description="Custom prompt for graph extraction",
        default=None,
    )

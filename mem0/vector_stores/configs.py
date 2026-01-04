from typing import Optional, Union
from pydantic import BaseModel, Field
from mem0.configs.vector_stores.supabase import SupabaseConfig

class VectorStoreConfig(BaseModel):
    provider: str = Field(
        description="Provider of the vector store (e.g. 'supabase')",
        default="supabase",
    )
    config: Optional[SupabaseConfig] = Field(
        description="Configuration for the specific vector store",
        default=None,
    )

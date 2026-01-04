from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class IndexMethod(str, Enum):
    AUTO = "auto"
    HNSW = "hnsw"
    IVFFLAT = "ivfflat"


class IndexMeasure(str, Enum):
    COSINE = "cosine_distance"
    L2 = "l2_distance"
    L1 = "l1_distance"
    MAX_INNER_PRODUCT = "max_inner_product"


import os

class SupabaseConfig(BaseModel):
    connection_string: Optional[str] = Field(None, description="PostgreSQL connection string")
    collection_name: str = Field("mem0", description="Name for the vector collection")

    @model_validator(mode="before")
    def set_defaults_from_env(cls, values):
        if not values.get("connection_string"):
            values["connection_string"] = os.environ.get("SUPABASE_CONNECTION_STRING") or os.environ.get("Vector_STORE_CONNECTION_STRING")
        if not values.get("collection_name"):
            values["collection_name"] = os.environ.get("SUPABASE_COLLECTION_NAME", "mem0")
        return values
    embedding_model_dims: Optional[int] = Field(1536, description="Dimensions of the embedding model")
    index_method: Optional[IndexMethod] = Field(IndexMethod.AUTO, description="Index method to use")
    index_measure: Optional[IndexMeasure] = Field(IndexMeasure.COSINE, description="Distance measure to use")

    @model_validator(mode="before")
    def check_connection_string(cls, values):
        conn_str = values.get("connection_string")
        if not conn_str or not conn_str.startswith("postgresql://"):
            raise ValueError("A valid PostgreSQL connection string must be provided")
        return values

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. Please input only the following fields: {', '.join(allowed_fields)}"
            )
        return values

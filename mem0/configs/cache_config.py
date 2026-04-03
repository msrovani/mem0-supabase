from pydantic import BaseModel
from typing import Optional


class CacheConfig(BaseModel):
    # Redis/L1 configuration
    redis_url: str = "redis://localhost:6379"
    redis_enabled: bool = False
    redis_ttl_seconds: int = 3600
    redis_quantization: str = "Q8"  # Q8, BIN, NOQUANT

    # L1/L2 decision thresholds (behavior may be used by HybridCache)
    l1_threshold: float = 0.95
    l2_threshold: float = 0.90

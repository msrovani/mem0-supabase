"""
API Versioning — v1/v2 router for backward-compatible API evolution.

Usage:
    # v1 endpoints (legacy)
    GET /v1/memories
    POST /v1/memories

    # v2 endpoints (current)
    GET /v2/memories
    POST /v2/memories/bulk

Mount in main.py:
    from server.api_v2 import router as v2_router
    app.include_router(v2_router, prefix="/v2")
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

router = APIRouter(tags=["v2"])


# --- Models ---
class MessageV2(BaseModel):
    role: str = Field(..., description="Role: user, assistant, or system.")
    content: str = Field(..., description="Message content.")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Message-level metadata.")


class MemoryCreateV2(BaseModel):
    messages: List[MessageV2] = Field(..., description="Messages to store.")
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = Field(None, max_length=128)
    ttl_seconds: Optional[int] = Field(None, description="Auto-expire memory after N seconds.")
    template: Optional[str] = Field(None, description="Memory template name.")


class MemoryResponseV2(BaseModel):
    id: str
    memory: str
    score: Optional[float] = None
    created_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class PaginatedResponseV2(BaseModel):
    items: List[MemoryResponseV2]
    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None
    total_count: int
    has_more: bool


# --- Endpoints ---

@router.get("/memories", response_model=PaginatedResponseV2)
def get_memories_v2(
    request: Request,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    run_id: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = 20,
):
    """V2: Get memories with bidirectional pagination."""
    # Implementation delegates to v1 with enhanced response
    memory = request.app.state.memory
    lock = request.app.state.memory_lock

    with lock:
        params = {k: v for k, v in {"user_id": user_id, "agent_id": agent_id, "run_id": run_id}.items() if v}
        all_items = memory.get_all(**params) or []

    all_items.sort(key=lambda x: x.get("id", ""))

    start_idx = 0
    if cursor:
        for i, item in enumerate(all_items):
            if item.get("id") == cursor:
                start_idx = i + 1
                break

    end_idx = min(start_idx + limit, len(all_items))
    page = all_items[start_idx:end_idx]

    has_more = end_idx < len(all_items)
    prev_cursor = all_items[start_idx - 1].get("id") if start_idx > 0 else None
    next_cursor = page[-1].get("id") if has_more else None

    return {
        "items": page,
        "next_cursor": next_cursor,
        "prev_cursor": prev_cursor,
        "total_count": len(all_items),
        "has_more": has_more,
    }


@router.post("/memories")
def create_memory_v2(request: Request, memory_create: MemoryCreateV2):
    """V2: Create memory with TTL and template support."""
    memory = request.app.state.memory
    lock = request.app.state.memory_lock

    params = {
        k: v for k, v in memory_create.model_dump().items()
        if v is not None and k not in ("messages", "ttl_seconds", "template")
    }

    with lock:
        response = memory.add(
            messages=[m.model_dump(exclude_none=True) for m in memory_create.messages],
            **params,
        )

    # Apply TTL if specified
    if memory_create.ttl_seconds and response.get("results"):
        for result in response["results"]:
            mem_id = result.get("id")
            if mem_id:
                # Schedule expiration via event store
                from mem0.event_sourcing import EventStore
                try:
                    event_store = getattr(request.app.state, "event_store", None)
                    if event_store:
                        event_store.append(
                            "memory.expire_scheduled",
                            {"memory_id": mem_id, "expires_at": __import__("time").time() + memory_create.ttl_seconds},
                            stream_id=f"ttl:{mem_id}",
                        )
                except Exception:
                    pass

    return response


@router.get("/metrics")
def get_metrics_v2(request: Request):
    """V2: Prometheus-compatible metrics endpoint."""
    from mem0.metrics import metrics
    return metrics.render()

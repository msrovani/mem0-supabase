"""
Mem0 REST API Server — Production-Grade

Features:
- Health check with live DB/LLM connectivity tests (#1)
- Graceful shutdown (#2)
- Idempotency keys (#3)
- Request ID tracing (#4)
- Response streaming (SSE) (#9)
- Bulk operations (#11)
- Per-user rate limiting (#15)
- X-Request-Id, Retry-After, Content-Type headers (#25-29)
- Input validation with regex (#28)
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import time
import threading
import uuid
from collections import OrderedDict
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from jose import JWTError, jwt

from mem0 import Memory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# --- ID Validation (#28) ---
_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]{1,128}$")


def _validate_id(value: str, field: str) -> str:
    if value and not _ID_PATTERN.match(value):
        raise ValueError(f"{field} must be 1-128 chars, alphanumeric with _-. only. Got: {value[:32]}...")
    return value


def _require_env(key: str) -> str:
    """Require an environment variable or fail-fast."""
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {key}. Never run with default credentials in production."
        )
    return value


# --- Configuration ---
POSTGRES_HOST = _require_env("POSTGRES_HOST")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_DB = _require_env("POSTGRES_DB")
POSTGRES_USER = _require_env("POSTGRES_USER")
POSTGRES_PASSWORD = _require_env("POSTGRES_PASSWORD")
POSTGRES_COLLECTION_NAME = os.environ.get("POSTGRES_COLLECTION_NAME", "memories")

NEO4J_URI = os.environ.get("NEO4J_URI")
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD")

MEMGRAPH_URI = os.environ.get("MEMGRAPH_URI")
MEMGRAPH_USERNAME = os.environ.get("MEMGRAPH_USERNAME")
MEMGRAPH_PASSWORD = os.environ.get("MEMGRAPH_PASSWORD")

OPENAI_API_KEY = _require_env("OPENAI_API_KEY")
JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    logger.warning(
        "JWT_SECRET not configured. Authenticated endpoints will return 500. Set JWT_SECRET to enable authentication."
    )

# Connection pool settings (#6)
POOL_MIN_SIZE = int(os.environ.get("DB_POOL_MIN", "2"))
POOL_MAX_SIZE = int(os.environ.get("DB_POOL_MAX", "20"))
POOL_TIMEOUT = int(os.environ.get("DB_POOL_TIMEOUT", "30"))

# Idempotency cache (#3)
_idempotency_store: OrderedDict[str, dict] = OrderedDict()
_idempotency_lock = threading.Lock()
_IDEMPOTENCY_TTL = 3600  # 1 hour
_IDEMPOTENCY_MAX_ENTRIES = 10000

DEFAULT_CONFIG = {
    "version": "v1.1",
    "vector_store": {
        "provider": "supabase",
        "config": {
            "connection_string": os.environ.get(
                "SUPABASE_CONNECTION_STRING",
                f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
            ),
            "collection_name": os.environ.get("SUPABASE_COLLECTION_NAME", "memories"),
        },
    },
    "graph_store": {
        "provider": "supabase",
        "config": {
            "connection_string": os.environ.get(
                "SUPABASE_CONNECTION_STRING",
                f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
            ),
        },
    },
    "llm": {
        "provider": "openai",
        "config": {"api_key": OPENAI_API_KEY, "temperature": 0.2, "model": "gpt-4.1-nano-2025-04-14"},
    },
    "embedder": {"provider": "openai", "config": {"api_key": OPENAI_API_KEY, "model": "text-embedding-3-small"}},
}

# --- Idempotency (#3) ---


def _get_idempotency_key(key: str) -> Optional[dict]:
    """Get cached idempotency response."""
    with _idempotency_lock:
        if key in _idempotency_store:
            entry = _idempotency_store[key]
            if time.time() - entry["time"] < _IDEMPOTENCY_TTL:
                _idempotency_store.move_to_end(key)
                return entry["response"]
            else:
                del _idempotency_store[key]
    return None


def _set_idempotency_key(key: str, response: dict) -> None:
    """Cache idempotency response with TTL."""
    with _idempotency_lock:
        _idempotency_store[key] = {"response": response, "time": time.time()}
        # Evict oldest if over limit
        while len(_idempotency_store) > _IDEMPOTENCY_MAX_ENTRIES:
            _idempotency_store.popitem(last=False)


def _evict_expired_idempotency() -> None:
    """Remove expired idempotency entries."""
    now = time.time()
    with _idempotency_lock:
        expired = [k for k, v in _idempotency_store.items() if now - v["time"] >= _IDEMPOTENCY_TTL]
        for k in expired:
            del _idempotency_store[k]


# --- Rate Limiter ---
limiter = Limiter(key_func=get_remote_address)


def _user_rate_limit_key(request: Request) -> str:
    """Rate limit by user ID if authenticated, else by IP (#15)."""
    try:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer ") and JWT_SECRET:
            token = auth_header.split(" ", 1)[1]
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            user_id = payload.get("sub") or payload.get("user_id")
            if user_id:
                return f"user:{user_id}"
    except Exception:
        pass
    return f"ip:{get_remote_address(request)}"


user_limiter = Limiter(key_func=_user_rate_limit_key)


# --- Graceful Shutdown (#2) ---
_shutdown_event = threading.Event()


async def _shutdown_tasks():
    """Cleanup tasks on shutdown."""
    logger.info("Initiating graceful shutdown...")
    _shutdown_event.set()
    _evict_expired_idempotency()
    logger.info("Graceful shutdown complete.")


# --- Lifespan (#1 + #2) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle with health checks and graceful shutdown."""
    # Startup
    app.state.memory = Memory.from_config(DEFAULT_CONFIG)
    app.state.memory_lock = threading.Lock()
    app.state.startup_time = time.time()
    logger.info("Mem0 Memory instance initialized (thread-safe mode)")

    # Run background idempotency cleanup every 10 minutes
    async def idempotency_cleanup():
        while not _shutdown_event.is_set():
            await asyncio.sleep(600)
            _evict_expired_idempotency()

    app.state.cleanup_task = asyncio.create_task(idempotency_cleanup())

    yield

    # Shutdown
    app.state.cleanup_task.cancel()
    try:
        await app.state.cleanup_task
    except asyncio.CancelledError:
        pass
    await _shutdown_tasks()


app = FastAPI(
    title="Mem0 REST APIs",
    description="Production-grade REST API for managing and searching memories for AI Agents and Apps.",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limit handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# --- Middleware: Request ID + Duration (#4, #25, #26) ---
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    # Generate or propagate request ID
    request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    request.state.request_id = request_id

    start_time = time.monotonic()

    response = await call_next(request)

    # Add headers (#25, #29)
    response.headers["X-Request-Id"] = request_id
    response.headers["Content-Type"] = "application/json"

    # Log duration (#26)
    duration_ms = (time.monotonic() - start_time) * 1000
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {duration_ms:.1f}ms - {request_id}")
    response.headers["X-Response-Time"] = f"{duration_ms:.1f}ms"

    return response


# --- Auth ---
def verify_token(request: Request) -> Dict[str, Any]:
    """Verify JWT Bearer token."""
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured on server.")

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header. Use: Bearer <token>")

    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        request.state.user = payload
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")


# --- Pydantic Models ---
class Message(BaseModel):
    role: str = Field(..., description="Role of the message (user or assistant).")
    content: str = Field(..., description="Message content.")


class MemoryCreate(BaseModel):
    messages: List[Message] = Field(..., description="List of messages to store.")
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = Field(None, description="Unique key for idempotent requests (#3)")

    @field_validator("user_id", "agent_id", "run_id")
    @classmethod
    def validate_ids(cls, v, info):
        if v is not None:
            return _validate_id(v, info.field_name)
        return v

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, v):
        if v is not None and len(v) > 128:
            raise ValueError("idempotency_key must be <= 128 chars")
        return v


class BulkMemoryCreate(BaseModel):
    """Bulk memory creation (#11)."""

    items: List[MemoryCreate] = Field(..., description="List of memory create requests.", max_length=100)

    @field_validator("items")
    @classmethod
    def validate_items(cls, v):
        if len(v) > 100:
            raise ValueError("Maximum 100 items per bulk request")
        return v


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query.")
    user_id: Optional[str] = None
    run_id: Optional[str] = None
    agent_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None


class StreamRequest(BaseModel):
    """Request for SSE streaming response (#9)."""

    messages: List[Message] = Field(..., description="List of messages to process.")
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# --- Helpers ---
def _get_memory(app: FastAPI):
    """Thread-safe memory instance accessor."""
    return app.state.memory, app.state.memory_lock


def _item_id(item: Dict[str, Any]) -> str:
    """Extract unique ID from a memory item."""
    return item.get("memory_id") or item.get("id") or ""


def _error_response(status_code: int, detail: str, request_id: str) -> JSONResponse:
    """Consistent error response with request ID."""
    return JSONResponse(
        status_code=status_code,
        content={"error": detail, "request_id": request_id},
    )


# --- Health Check (#1) ---
@app.get("/health", summary="Health check with live connectivity tests")
@limiter.limit("60/minute")
async def health(request: Request):
    """
    Comprehensive health check (#1):
    - Returns config info
    - Tests DB connectivity
    - Tests LLM connectivity
    - Reports uptime
    """
    memory, lock = _get_memory(request.app)
    checks = {
        "version": DEFAULT_CONFIG.get("version"),
        "vector_store": DEFAULT_CONFIG.get("vector_store", {}).get("provider"),
        "graph_store": DEFAULT_CONFIG.get("graph_store", {}).get("provider"),
        "llm": DEFAULT_CONFIG.get("llm", {}).get("provider"),
        "embedder": DEFAULT_CONFIG.get("embedder", {}).get("provider"),
        "uptime_seconds": round(time.time() - getattr(request.app.state, "startup_time", 0), 1),
    }

    # Test DB connectivity
    db_ok = False
    try:
        with lock:
            memory.get_all(user_id="__health_check__", limit=0)
        db_ok = True
    except Exception as e:
        logger.warning(f"Health check DB test failed: {e}")

    checks["database"] = "connected" if db_ok else "unreachable"

    # Test LLM connectivity (lightweight)
    llm_ok = False
    try:
        with lock:
            memory.llm.generate_response(messages=[{"role": "user", "content": "ok"}])
        llm_ok = True
    except Exception as e:
        logger.warning(f"Health check LLM test failed: {e}")

    checks["llm"] = "connected" if llm_ok else "unreachable"

    status = 200 if (db_ok and llm_ok) else 503
    checks["status"] = "healthy" if status == 200 else "degraded"

    return JSONResponse(status_code=status, content=checks)


# --- Configure ---
@app.post("/configure", summary="Configure Mem0 (thread-safe)")
@user_limiter.limit("10/minute")
def set_config(request: Request, config: Dict[str, Any], _token: None = Depends(verify_token)):
    """Set memory configuration (thread-safe)."""
    memory, lock = _get_memory(request.app)
    with lock:
        request.app.state.memory = Memory.from_config(config)
        request.app.state.memory_lock = lock
    return {"message": "Configuration set successfully"}


# --- Create Memory (#3: Idempotency) ---
@app.post("/memories", summary="Create memories (with idempotency support)")
@user_limiter.limit("60/minute")
def add_memory(request: Request, memory_create: MemoryCreate, _token: None = Depends(verify_token)):
    """Store new memories with optional idempotency key."""
    if not any([memory_create.user_id, memory_create.agent_id, memory_create.run_id]):
        raise HTTPException(
            status_code=400,
            detail="At least one identifier (user_id, agent_id, run_id) is required.",
        )

    # Idempotency check (#3)
    if memory_create.idempotency_key:
        cached = _get_idempotency_key(memory_create.idempotency_key)
        if cached is not None:
            return JSONResponse(content=cached)

    memory, lock = _get_memory(request.app)
    params = {
        k: v
        for k, v in memory_create.model_dump().items()
        if v is not None and k not in ("messages", "idempotency_key")
    }
    try:
        with lock:
            response = memory.add(messages=[m.model_dump() for m in memory_create.messages], **params)

        # Cache response for idempotency
        if memory_create.idempotency_key:
            _set_idempotency_key(memory_create.idempotency_key, response)

        return JSONResponse(content=response)
    except Exception as e:
        logger.exception("Error in add_memory:")
        raise HTTPException(status_code=500, detail=str(e))


# --- Bulk Create (#11) ---
@app.post("/memories/bulk", summary="Bulk create memories (up to 100)")
@user_limiter.limit("10/minute")
def bulk_add_memory(request: Request, bulk: BulkMemoryCreate, _token: None = Depends(verify_token)):
    """Create multiple memories in a single request (#11)."""
    memory, lock = _get_memory(request.app)
    results = []
    errors = []

    for i, item in enumerate(bulk.items):
        try:
            # Idempotency check
            if item.idempotency_key:
                cached = _get_idempotency_key(item.idempotency_key)
                if cached is not None:
                    results.append({"index": i, "status": "cached", "data": cached})
                    continue

            params = {
                k: v for k, v in item.model_dump().items() if v is not None and k not in ("messages", "idempotency_key")
            }
            with lock:
                response = memory.add(messages=[m.model_dump() for m in item.messages], **params)

            if item.idempotency_key:
                _set_idempotency_key(item.idempotency_key, response)

            results.append({"index": i, "status": "created", "data": response})
        except Exception as e:
            errors.append({"index": i, "error": str(e)})

    return {
        "created": len(results),
        "errors": len(errors),
        "results": results,
        "error_details": errors,
    }


# --- SSE Streaming (#9) ---
@app.post("/memories/stream", summary="Create memories with SSE progress streaming")
@user_limiter.limit("30/minute")
async def stream_add_memory(request: Request, stream_req: StreamRequest, _token: None = Depends(verify_token)):
    """
    Create memories with Server-Sent Events progress updates (#9).
    Clients receive real-time feedback as each step completes.
    """
    if not any([stream_req.user_id, stream_req.agent_id, stream_req.run_id]):
        raise HTTPException(
            status_code=400,
            detail="At least one identifier (user_id, agent_id, run_id) is required.",
        )

    async def event_stream():
        """SSE event generator."""
        memory, lock = _get_memory(request.app)
        params = {
            k: v
            for k, v in {
                "user_id": stream_req.user_id,
                "agent_id": stream_req.agent_id,
                "run_id": stream_req.run_id,
                "metadata": stream_req.metadata,
            }.items()
            if v is not None
        }

        # Step 1: Validate
        yield f"data: {json.dumps({'step': 'validating', 'message': 'Validating input...'})}\n\n"
        await asyncio.sleep(0)

        # Step 2: Embed
        yield f"data: {json.dumps({'step': 'embedding', 'message': 'Generating embeddings...'})}\n\n"
        await asyncio.sleep(0)

        # Step 3: Store
        try:
            with lock:
                response = memory.add(
                    messages=[m.model_dump() for m in stream_req.messages],
                    **params,
                )

            yield f"data: {json.dumps({'step': 'stored', 'message': 'Memories stored successfully.', 'result': response})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'step': 'error', 'message': str(e)})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- Get All (paginated) ---
@app.get("/memories", summary="Get memories (paginated)")
@user_limiter.limit("30/minute")
def get_all_memories(
    request: Request,
    user_id: Optional[str] = None,
    run_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = 20,
    _token: None = Depends(verify_token),
):
    """Retrieve stored memories with cursor-based pagination."""
    if not any([user_id, run_id, agent_id]):
        raise HTTPException(status_code=400, detail="At least one identifier is required.")

    limit = min(max(limit, 1), 100)

    memory, lock = _get_memory(request.app)
    try:
        with lock:
            params = {
                k: v for k, v in {"user_id": user_id, "run_id": run_id, "agent_id": agent_id}.items() if v is not None
            }
            all_items = memory.get_all(**params) or []

        all_items.sort(key=_item_id)

        start_idx = 0
        if cursor:
            for i, item in enumerate(all_items):
                if _item_id(item) == cursor:
                    start_idx = i + 1
                    break

        page = all_items[start_idx : start_idx + limit]
        next_cursor = _item_id(page[-1]) if len(page) == limit and start_idx + limit < len(all_items) else None

        return {
            "items": page,
            "next_cursor": next_cursor,
            "total_count": len(all_items),
        }
    except Exception as e:
        logger.exception("Error in get_all_memories:")
        raise HTTPException(status_code=500, detail=str(e))


# --- Get Single ---
@app.get("/memories/{memory_id}", summary="Get a memory")
@user_limiter.limit("60/minute")
def get_memory(request: Request, memory_id: str, _token: None = Depends(verify_token)):
    """Retrieve a specific memory by ID."""
    memory, lock = _get_memory(request.app)
    try:
        with lock:
            return memory.get(memory_id)
    except Exception as e:
        logger.exception("Error in get_memory:")
        raise HTTPException(status_code=500, detail=str(e))


# --- Search ---
@app.post("/search", summary="Search memories")
@user_limiter.limit("30/minute")
def search_memories(request: Request, search_req: SearchRequest, _token: None = Depends(verify_token)):
    """Search for memories based on a query."""
    memory, lock = _get_memory(request.app)
    try:
        with lock:
            params = {k: v for k, v in search_req.model_dump().items() if v is not None and k != "query"}
            return memory.search(query=search_req.query, **params)
    except Exception as e:
        logger.exception("Error in search_memories:")
        raise HTTPException(status_code=500, detail=str(e))


# --- Update ---
@app.put("/memories/{memory_id}", summary="Update a memory")
@user_limiter.limit("30/minute")
def update_memory(
    request: Request, memory_id: str, updated_memory: Dict[str, Any], _token: None = Depends(verify_token)
):
    """Update an existing memory with new content."""
    memory, lock = _get_memory(request.app)
    try:
        with lock:
            return memory.update(memory_id=memory_id, data=updated_memory)
    except Exception as e:
        logger.exception("Error in update_memory:")
        raise HTTPException(status_code=500, detail=str(e))


# --- History ---
@app.get("/memories/{memory_id}/history", summary="Get memory history")
@user_limiter.limit("60/minute")
def memory_history(request: Request, memory_id: str, _token: None = Depends(verify_token)):
    """Retrieve memory history."""
    memory, lock = _get_memory(request.app)
    try:
        with lock:
            return memory.history(memory_id=memory_id)
    except Exception as e:
        logger.exception("Error in memory_history:")
        raise HTTPException(status_code=500, detail=str(e))


# --- Delete Single ---
@app.delete("/memories/{memory_id}", summary="Delete a memory")
@user_limiter.limit("30/minute")
def delete_memory(request: Request, memory_id: str, _token: None = Depends(verify_token)):
    """Delete a specific memory by ID."""
    memory, lock = _get_memory(request.app)
    try:
        with lock:
            memory.delete(memory_id=memory_id)
        return {"message": "Memory deleted successfully"}
    except Exception as e:
        logger.exception("Error in delete_memory:")
        raise HTTPException(status_code=500, detail=str(e))


# --- Delete All ---
@app.delete("/memories", summary="Delete all memories")
@user_limiter.limit("10/minute")
def delete_all_memories(
    request: Request,
    user_id: Optional[str] = None,
    run_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    _token: None = Depends(verify_token),
):
    """Delete all memories for a given identifier."""
    if not any([user_id, run_id, agent_id]):
        raise HTTPException(status_code=400, detail="At least one identifier is required.")

    memory, lock = _get_memory(request.app)
    try:
        with lock:
            params = {
                k: v for k, v in {"user_id": user_id, "run_id": run_id, "agent_id": agent_id}.items() if v is not None
            }
            memory.delete_all(**params)
        return {"message": "All relevant memories deleted"}
    except Exception as e:
        logger.exception("Error in delete_all_memories:")
        raise HTTPException(status_code=500, detail=str(e))


# --- Reset ---
@app.post("/reset", summary="Reset all memories")
@user_limiter.limit("5/minute")
def reset_memory(request: Request, _token: None = Depends(verify_token)):
    """Completely reset stored memories."""
    memory, lock = _get_memory(request.app)
    try:
        with lock:
            memory.reset()
        return {"message": "All memories reset"}
    except Exception as e:
        logger.exception("Error in reset_memory:")
        raise HTTPException(status_code=500, detail=str(e))


# --- Home ---
@app.get("/", summary="Redirect to the OpenAPI documentation", include_in_schema=False)
def home():
    """Redirect to the OpenAPI documentation."""
    return RedirectResponse(url="/docs")

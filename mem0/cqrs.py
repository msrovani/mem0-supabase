"""
CQRS Foundation — Command/Query Responsibility Segregation for memory operations.

Separates write operations (Commands) from read operations (Queries) to enable:
- Independent scaling of read/write paths
- Optimized read models (denormalized, indexed)
- Write models with full validation and business logic
- Event-driven synchronization between models

Usage:
    from mem0.cqrs import CommandBus, QueryBus

    commands = CommandBus()
    commands.register("create_memory", CreateMemoryHandler(memory_store))
    result = commands.execute("create_memory", {"content": "...", "user_id": "u1"})

    queries = QueryBus()
    queries.register("search_memories", SearchMemoriesHandler(read_store))
    results = queries.execute("search_memories", {"query": "pizza", "user_id": "u1"})
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "Command",
    "CommandResult",
    "CommandBus",
    "Query",
    "QueryResult",
    "QueryBus",
]


@dataclass
class Command:
    """A write command with validation."""

    name: str
    payload: Dict[str, Any]
    request_id: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class CommandResult:
    """Result of a command execution."""

    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0


@dataclass
class Query:
    """A read query."""

    name: str
    payload: Dict[str, Any]
    request_id: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class QueryResult:
    """Result of a query execution."""

    data: Any
    execution_time_ms: float = 0.0
    cache_hit: bool = False


class CommandHandler(ABC):
    """Abstract base for command handlers."""

    @abstractmethod
    def handle(self, command: Command) -> CommandResult:
        """Execute the command and return result."""


class QueryHandler(ABC):
    """Abstract base for query handlers."""

    @abstractmethod
    def handle(self, query: Query) -> QueryResult:
        """Execute the query and return result."""


class CommandBus:
    """
    Thread-safe command bus with handler registration and execution tracking.
    """

    def __init__(self):
        self._handlers: Dict[str, CommandHandler] = {}
        self._lock = threading.Lock()
        self._execution_count = 0
        self._total_time_ms = 0.0

    def register(self, name: str, handler: CommandHandler) -> None:
        """Register a command handler."""
        with self._lock:
            self._handlers[name] = handler

    def execute(self, name: str, payload: Dict[str, Any], request_id: str = "") -> CommandResult:
        """
        Execute a command by name.

        Args:
            name: Command name (must have registered handler).
            payload: Command payload.
            request_id: Optional request correlation ID.

        Returns:
            CommandResult with success status and data/error.
        """
        start = time.monotonic()

        with self._lock:
            handler = self._handlers.get(name)

        if handler is None:
            return CommandResult(
                success=False,
                error=f"No handler registered for command: {name}",
            )

        try:
            command = Command(name=name, payload=payload, request_id=request_id)
            result = handler.handle(command)
            result.execution_time_ms = (time.monotonic() - start) * 1000

            with self._lock:
                self._execution_count += 1
                self._total_time_ms += result.execution_time_ms

            if not result.success:
                logger.warning(f"Command '{name}' failed: {result.error}")

            return result
        except Exception as e:
            logger.exception(f"Command '{name}' execution error:")
            return CommandResult(
                success=False,
                error=str(e),
                execution_time_ms=(time.monotonic() - start) * 1000,
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get command bus statistics."""
        with self._lock:
            return {
                "registered_handlers": list(self._handlers.keys()),
                "total_executions": self._execution_count,
                "avg_execution_time_ms": round(self._total_time_ms / max(self._execution_count, 1), 2),
            }


class QueryBus:
    """
    Thread-safe query bus with handler registration and optional caching.
    """

    def __init__(self, enable_cache: bool = False, cache_ttl: float = 60.0):
        """
        Initialize QueryBus.

        Args:
            enable_cache: Enable query result caching.
            cache_ttl: Cache time-to-live in seconds.
        """
        self._handlers: Dict[str, QueryHandler] = {}
        self._cache: Dict[str, tuple] = {}  # key -> (result, expires_at)
        self._cache_enabled = enable_cache
        self._cache_ttl = cache_ttl
        self._lock = threading.Lock()
        self._execution_count = 0
        self._cache_hits = 0

    def register(self, name: str, handler: QueryHandler) -> None:
        """Register a query handler."""
        with self._lock:
            self._handlers[name] = handler

    def execute(self, name: str, payload: Dict[str, Any], request_id: str = "") -> QueryResult:
        """
        Execute a query by name.

        Args:
            name: Query name (must have registered handler).
            payload: Query payload.
            request_id: Optional request correlation ID.

        Returns:
            QueryResult with data and execution time.
        """
        import hashlib
        import json

        cache_key = hashlib.sha256(f"{name}:{json.dumps(payload, sort_keys=True)}".encode()).hexdigest()[:16]

        # Check cache
        if self._cache_enabled:
            with self._lock:
                if cache_key in self._cache:
                    result, expires_at = self._cache[cache_key]
                    if time.time() < expires_at:
                        self._cache_hits += 1
                        return QueryResult(data=result, cache_hit=True)

        start = time.monotonic()

        with self._lock:
            handler = self._handlers.get(name)

        if handler is None:
            raise ValueError(f"No handler registered for query: {name}")

        query = Query(name=name, payload=payload, request_id=request_id)
        result = handler.handle(query)
        result.execution_time_ms = (time.monotonic() - start) * 1000

        # Cache result
        if self._cache_enabled:
            with self._lock:
                self._cache[cache_key] = (result.data, time.time() + self._cache_ttl)

        with self._lock:
            self._execution_count += 1

        return result

    def invalidate_cache(self, name: Optional[str] = None) -> None:
        """Invalidate cached query results."""
        with self._lock:
            if name:
                # Remove entries for this query type
                self._cache = {
                    k: v
                    for k, v in self._cache.items()
                    if not k.startswith(hashlib.sha256(f"{name}:".encode()).hexdigest()[:8])
                }
            else:
                self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get query bus statistics."""
        import hashlib

        with self._lock:
            return {
                "registered_handlers": list(self._handlers.keys()),
                "total_executions": self._execution_count,
                "cache_hits": self._cache_hits,
                "cache_hit_rate": round(self._cache_hits / max(self._execution_count, 1), 4),
                "cache_size": len(self._cache),
            }

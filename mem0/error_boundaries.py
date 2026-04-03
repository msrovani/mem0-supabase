"""
Error Boundaries — Lightweight Circuit Breaker for External Services

Protects the memory system from cascading failures when LLM, vector store,
or graph store providers become unavailable.

Usage:
    from mem0.error_boundaries import CircuitBreaker

    llm_breaker = CircuitBreaker(name="llm", failure_threshold=3, recovery_timeout=30)

    @llm_breaker
    def call_llm(messages):
        return llm.generate_response(messages=messages)

    result = call_llm([{"role": "user", "content": "hello"}])
"""

import logging
import threading
import time
from functools import wraps
from typing import Any, Callable, Optional

__all__ = [
    "CircuitState",
    "CircuitBreakerError",
    "CircuitBreaker",
    "get_llm_breaker",
    "get_vector_store_breaker",
    "get_graph_breaker",
    "get_all_breaker_stats",
]

logger = logging.getLogger(__name__)


class CircuitState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerError(Exception):
    """Raised when circuit is open and call is rejected."""

    pass


class CircuitBreaker:
    """
    Lightweight circuit breaker for external service calls.

    States:
    - CLOSED: Normal operation. Failures are counted.
    - OPEN: Service is considered down. All calls fail immediately.
    - HALF_OPEN: Testing if service recovered. One call is allowed through.

    Transitions:
    - CLOSED -> OPEN: When failure_count >= failure_threshold
    - OPEN -> HALF_OPEN: After recovery_timeout seconds
    - HALF_OPEN -> CLOSED: On successful call
    - HALF_OPEN -> OPEN: On failed call
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: int = 30,
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Identifier for logging (e.g., "llm", "vector_store", "graph").
            failure_threshold: Number of consecutive failures before opening circuit.
            recovery_timeout: Seconds to wait before testing recovery.
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._total_calls = 0
        self._total_failures = 0
        self._total_rejected = 0

    def __call__(self, func: Callable) -> Callable:
        """Decorator: wrap a function with circuit breaker protection."""

        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)

        return wrapper

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function through the circuit breaker.

        Args:
            func: The function to call.
            *args, **kwargs: Arguments passed to func.

        Returns:
            The result of func(*args, **kwargs).

        Raises:
            CircuitBreakerError: If circuit is open.
            Exception: Re-raises the original exception if call fails.
        """
        with self._lock:
            self._total_calls += 1

            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has elapsed
                if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    logger.info(f"CircuitBreaker[{self.name}]: transitioning to HALF_OPEN (testing recovery)")
                else:
                    self._total_rejected += 1
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Service unavailable. Retry in {self.recovery_timeout}s."
                    )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except CircuitBreakerError:
            raise
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Handle successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info(f"CircuitBreaker[{self.name}]: recovered, transitioning to CLOSED")
            else:
                self._failure_count = 0

    def _on_failure(self) -> None:
        """Handle failed call."""
        with self._lock:
            self._total_failures += 1
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(f"CircuitBreaker[{self.name}]: recovery test failed, transitioning to OPEN")
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"CircuitBreaker[{self.name}]: {self._failure_count} consecutive failures, "
                    f"transitioning to OPEN (recovery in {self.recovery_timeout}s)"
                )

    @property
    def state(self) -> str:
        """Current circuit state."""
        return self._state

    @property
    def is_open(self) -> bool:
        """Whether the circuit is open (service unavailable)."""
        return self._state == CircuitState.OPEN

    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state,
                "failure_count": self._failure_count,
                "total_calls": self._total_calls,
                "total_failures": self._total_failures,
                "total_rejected": self._total_rejected,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
            }

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = 0.0
        logger.info(f"CircuitBreaker[{self.name}]: manually reset to CLOSED")


# Global circuit breakers for core services
_llm_breaker: Optional[CircuitBreaker] = None
_vector_store_breaker: Optional[CircuitBreaker] = None
_graph_breaker: Optional[CircuitBreaker] = None
_breakers_lock = threading.Lock()


def get_llm_breaker(
    failure_threshold: int = 3,
    recovery_timeout: int = 30,
) -> CircuitBreaker:
    """Get or create the global LLM circuit breaker."""
    global _llm_breaker
    if _llm_breaker is None:
        with _breakers_lock:
            if _llm_breaker is None:
                _llm_breaker = CircuitBreaker(
                    name="llm",
                    failure_threshold=failure_threshold,
                    recovery_timeout=recovery_timeout,
                )
    return _llm_breaker


def get_vector_store_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 15,
) -> CircuitBreaker:
    """Get or create the global vector store circuit breaker."""
    global _vector_store_breaker
    if _vector_store_breaker is None:
        with _breakers_lock:
            if _vector_store_breaker is None:
                _vector_store_breaker = CircuitBreaker(
                    name="vector_store",
                    failure_threshold=failure_threshold,
                    recovery_timeout=recovery_timeout,
                )
    return _vector_store_breaker


def get_graph_breaker(
    failure_threshold: int = 3,
    recovery_timeout: int = 30,
) -> CircuitBreaker:
    """Get or create the global graph store circuit breaker."""
    global _graph_breaker
    if _graph_breaker is None:
        with _breakers_lock:
            if _graph_breaker is None:
                _graph_breaker = CircuitBreaker(
                    name="graph",
                    failure_threshold=failure_threshold,
                    recovery_timeout=recovery_timeout,
                )
    return _graph_breaker


def get_all_breaker_stats() -> dict:
    """Get stats for all global circuit breakers."""
    return {
        "llm": _llm_breaker.get_stats() if _llm_breaker else None,
        "vector_store": _vector_store_breaker.get_stats() if _vector_store_breaker else None,
        "graph": _graph_breaker.get_stats() if _graph_breaker else None,
    }

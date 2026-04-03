"""
Retry utilities with exponential backoff for external service calls.

Usage:
    from mem0.retry_utils import retry_with_backoff

    @retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
    def call_llm(messages):
        return llm.generate_response(messages=messages)

    # Or use as a context wrapper:
    result = retry_with_backoff()(lambda: llm.generate_response(messages=[...]))
"""

import logging
import time
import functools
from typing import Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)

# Default retryable exceptions
_DEFAULT_RETRYABLE: Tuple[Type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
):
    """
    Decorator that retries a function with exponential backoff and optional jitter.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds between retries.
        max_delay: Maximum delay in seconds (caps exponential growth).
        exponential_base: Base for exponential calculation (default 2.0 = doubling).
        jitter: Add random jitter to prevent thundering herd (default True).
        retryable_exceptions: Tuple of exception types that trigger retries.
            Defaults to (ConnectionError, TimeoutError, OSError).

    Returns:
        Decorated function with retry logic.

    Example:
        @retry_with_backoff(max_retries=3, base_delay=0.5)
        def fetch_data(url):
            return requests.get(url, timeout=10)
    """
    if retryable_exceptions is None:
        retryable_exceptions = _DEFAULT_RETRYABLE

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import random

            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(f"Function '{func.__name__}' failed after {max_retries} retries: {e}")
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base**attempt), max_delay)

                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay = delay * (0.5 + random.random() * 0.5)

                    logger.warning(
                        f"Function '{func.__name__}' failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)

            # Should never reach here, but satisfy type checker
            raise last_exception  # type: ignore[misc]

        return wrapper

    return decorator


def retry_async_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
):
    """
    Async version of retry_with_backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds between retries.
        max_delay: Maximum delay in seconds.
        exponential_base: Base for exponential calculation.
        jitter: Add random jitter.
        retryable_exceptions: Exception types that trigger retries.

    Returns:
        Decorated async function with retry logic.
    """
    if retryable_exceptions is None:
        retryable_exceptions = _DEFAULT_RETRYABLE

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            import asyncio
            import random

            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(f"Async function '{func.__name__}' failed after {max_retries} retries: {e}")
                        raise

                    delay = min(base_delay * (exponential_base**attempt), max_delay)
                    if jitter:
                        delay = delay * (0.5 + random.random() * 0.5)

                    logger.warning(
                        f"Async function '{func.__name__}' failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)

            raise last_exception  # type: ignore[misc]

        return wrapper

    return decorator

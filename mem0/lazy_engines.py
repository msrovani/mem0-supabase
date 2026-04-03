"""
Lazy Engine Registry — On-demand initialization of memory engines.

Replaces eager initialization with lazy loading to reduce startup time
and memory footprint. Engines are only created when first accessed.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = ["LazyEngineRegistry"]


class LazyEngineRegistry:
    """
    Thread-safe lazy initialization registry for memory engines.

    Usage:
        registry = LazyEngineRegistry()
        registry.register("reflection", lambda: ReflectionEngine(llm=llm))
        registry.register("dreaming", lambda: DreamingEngine(llm=llm))

        # Only creates when first accessed
        reflection = registry.get("reflection")
        dreaming = registry.get("dreaming")

        print(registry.get_stats())
    """

    def __init__(self):
        """Initialize empty registry."""
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._instances: Dict[str, Any] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def register(self, name: str, factory: Callable[[], Any]) -> None:
        """
        Register an engine factory for lazy initialization.

        Args:
            name: Engine identifier (e.g., "reflection", "dreaming").
            factory: Callable that returns the engine instance.
        """
        with self._global_lock:
            self._factories[name] = factory
            if name not in self._locks:
                self._locks[name] = threading.Lock()
            # Remove existing instance if re-registering
            self._instances.pop(name, None)

    def get(self, name: str) -> Optional[Any]:
        """
        Get or create an engine instance (lazy init with double-checked locking).

        Args:
            name: Engine identifier.

        Returns:
            Engine instance, or None if not registered.
        """
        # Fast path: already initialized
        if name in self._instances:
            return self._instances[name]

        # Check if registered
        if name not in self._factories:
            logger.debug(f"Engine '{name}' not registered in LazyEngineRegistry")
            return None

        # Double-checked locking
        lock = self._locks.get(name)
        if lock is None:
            return None

        with lock:
            # Check again inside lock
            if name in self._instances:
                return self._instances[name]

            try:
                logger.debug(f"Lazy-initializing engine: {name}")
                instance = self._factories[name]()
                self._instances[name] = instance
                return instance
            except Exception as e:
                logger.error(f"Failed to lazy-initialize engine '{name}': {e}")
                return None

    def is_initialized(self, name: str) -> bool:
        """Check if an engine has been initialized."""
        return name in self._instances

    def list_available(self) -> List[str]:
        """Return list of all registered engine names."""
        return list(self._factories.keys())

    def list_initialized(self) -> List[str]:
        """Return list of initialized engine names."""
        return list(self._instances.keys())

    def get_stats(self) -> Dict[str, Any]:
        """
        Get registry statistics.

        Returns:
            Dict with available, initialized, and engine details.
        """
        return {
            "available": len(self._factories),
            "initialized": len(self._instances),
            "engines": {name: "initialized" if name in self._instances else "registered" for name in self._factories},
        }

    def reset(self, name: Optional[str] = None) -> None:
        """
        Reset engine instance(s) for re-initialization.

        Args:
            name: Specific engine to reset, or None to reset all.
        """
        if name:
            self._instances.pop(name, None)
            logger.debug(f"Reset engine: {name}")
        else:
            self._instances.clear()
            logger.debug("Reset all engine instances")

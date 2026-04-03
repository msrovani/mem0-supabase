"""
Event Sourcing Foundation — Immutable event log for all memory mutations.

Every create/update/delete is recorded as an immutable event, enabling:
- Full audit trail
- State reconstruction via event replay
- Temporal queries (state at time T)
- Debugging and rollback

Usage:
    from mem0.event_sourcing import EventStore, MemoryEvent

    store = EventStore()
    event = store.append("memory.create", {"memory_id": "123", "data": "User likes pizza"})
    state = store.replay("memory", stream_id="user1")
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = ["MemoryEvent", "EventStore"]


@dataclass(slots=True)
class MemoryEvent:
    """An immutable event in the memory event log."""

    id: str
    event_type: str
    stream_id: str
    data: Dict[str, Any]
    timestamp: float
    version: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "stream_id": self.stream_id,
            "data": self.data,
            "timestamp": self.timestamp,
            "version": self.version,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MemoryEvent":
        return cls(
            id=d["id"],
            event_type=d["event_type"],
            stream_id=d["stream_id"],
            data=d["data"],
            timestamp=d["timestamp"],
            version=d["version"],
            metadata=d.get("metadata", {}),
        )


class EventStore:
    """
    Append-only event store for memory operations.

    Thread-safe. Supports event replay, stream querying, and projections.
    """

    def __init__(self, max_events_per_stream: int = 10000):
        """
        Initialize EventStore.

        Args:
            max_events_per_stream: Max events per stream before compaction.
        """
        self._streams: Dict[str, List[MemoryEvent]] = {}
        self._global_log: List[MemoryEvent] = []
        self._lock = threading.Lock()
        self._max_events = max_events_per_stream
        self._projections: Dict[str, Callable[[MemoryEvent], None]] = {}

    def append(
        self,
        event_type: str,
        data: Dict[str, Any],
        stream_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryEvent:
        """
        Append an event to a stream.

        Args:
            event_type: Event type (e.g., "memory.create", "memory.update").
            data: Event payload.
            stream_id: Stream identifier (e.g., user_id).
            metadata: Optional event metadata.

        Returns:
            The created MemoryEvent.
        """
        with self._lock:
            if stream_id not in self._streams:
                self._streams[stream_id] = []

            version = len(self._streams[stream_id]) + 1
            event = MemoryEvent(
                id=str(uuid.uuid4()),
                event_type=event_type,
                stream_id=stream_id,
                data=data,
                timestamp=time.time(),
                version=version,
                metadata=metadata or {},
            )

            self._streams[stream_id].append(event)
            self._global_log.append(event)

            # Run projections
            for proj in self._projections.values():
                try:
                    proj(event)
                except Exception as e:
                    logger.error(f"Projection failed for event {event.id}: {e}")

        return event

    def get_stream(self, stream_id: str, from_version: int = 0) -> List[MemoryEvent]:
        """Get events from a stream, optionally from a specific version."""
        with self._lock:
            events = self._streams.get(stream_id, [])
            if from_version > 0:
                events = [e for e in events if e.version > from_version]
            return list(events)

    def replay(self, event_type: str, stream_id: Optional[str] = None) -> List[MemoryEvent]:
        """Replay events of a specific type, optionally filtered by stream."""
        with self._lock:
            events = self._global_log
            if stream_id:
                events = [e for e in events if e.stream_id == stream_id]
            return [e for e in events if e.event_type == event_type]

    def get_state(self, stream_id: str) -> Dict[str, Any]:
        """
        Reconstruct current state by replaying all events in a stream.

        Returns a dict representing the latest state.
        """
        events = self.get_stream(stream_id)
        state: Dict[str, Any] = {}

        for event in events:
            if event.event_type.endswith(".create"):
                state.update(event.data)
            elif event.event_type.endswith(".update"):
                state.update(event.data)
            elif event.event_type.endswith(".delete"):
                state.clear()

        return state

    def register_projection(self, name: str, handler: Callable[[MemoryEvent], None]) -> None:
        """
        Register a projection that processes every appended event.

        Args:
            name: Projection name.
            handler: Callable that processes an event.
        """
        with self._lock:
            self._projections[name] = handler

    def get_stats(self) -> Dict[str, Any]:
        """Get event store statistics."""
        with self._lock:
            return {
                "total_streams": len(self._streams),
                "total_events": len(self._global_log),
                "streams": {sid: len(events) for sid, events in self._streams.items()},
                "projections": list(self._projections.keys()),
            }

from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class ActorContext(BaseModel):
    """Context describing the actor and its scope for memory tagging."""

    actor_id: Optional[str] = None
    actor_type: Optional[str] = None  # e.g., 'user', 'agent', 'system'
    conversation_id: Optional[str] = None
    run_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ActorAwareMemory:
    """Mixin providing actor-aware tagging utilities for memory items."""

    def tag_memory_with_actor(self, memory_item, actor_context: ActorContext):
        # Attach actor provenance to a memory item if compatible
        if memory_item is None:
            return None

        # Ensure attributes exist (tolerate missing attributes on older memory items)
        setattr(
            memory_item,
            "actor_id",
            getattr(memory_item, "actor_id", None) or actor_context.actor_id,
        )
        setattr(
            memory_item,
            "actor_type",
            getattr(memory_item, "actor_type", None) or actor_context.actor_type,
        )
        setattr(
            memory_item,
            "conversation_id",
            getattr(memory_item, "conversation_id", None)
            or actor_context.conversation_id,
        )
        setattr(
            memory_item,
            "run_id",
            getattr(memory_item, "run_id", None) or actor_context.run_id,
        )

        # Provenance field captures actor attribution for ground-truth isolation
        provenance = getattr(memory_item, "provenance", None) or {}
        if actor_context.actor_id is not None:
            provenance["actor_id"] = actor_context.actor_id
        if actor_context.actor_type is not None:
            provenance["actor_type"] = actor_context.actor_type
        setattr(memory_item, "provenance", provenance)

        # Optional: merge any provided actor metadata
        if actor_context.metadata:
            existing_meta = getattr(memory_item, "memory_metadata", None)
            if isinstance(existing_meta, dict):
                existing_meta.update(actor_context.metadata)
            else:
                setattr(memory_item, "memory_metadata", actor_context.metadata)
        return memory_item


def tag_memory_with_actor(memory_item, actor_context: ActorContext):
    return ActorAwareMemory().tag_memory_with_actor(memory_item, actor_context)


def filter_memories_by_actor(memories: List[Any], actor_context: ActorContext):
    """Return memories filtered to the given actor_id. If no actor_id provided, return as-is."""
    if not actor_context or not actor_context.actor_id:
        return memories
    return [
        m for m in memories if getattr(m, "actor_id", None) == actor_context.actor_id
    ]


def get_actor_conversation_history(
    actor_id: str, conversation_id: Optional[str], limit: int = 20
):
    """Utility to fetch conversation history for an actor. This is a thin wrapper
    intended to be wired to the storage backend; return an empty list if not wired."""
    # Placeholder implementation; actual data retrieval should be performed by
    # the storage layer (Postgres/SQLite) via actor-scoped queries.
    return [] if not actor_id else []

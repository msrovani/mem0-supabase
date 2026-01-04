"""
LangGraph Integration for Mem0-Supabase

Provides PostgresSaver-compatible checkpointing using the same Supabase database,
allowing LangGraph agents to persist their state alongside memories.
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime

try:
    from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    BaseCheckpointSaver = object
    Checkpoint = dict

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


class Mem0CheckpointSaver(BaseCheckpointSaver if LANGGRAPH_AVAILABLE else object):
    """
    LangGraph checkpoint saver that uses the same Supabase database as Mem0.
    
    This allows agents built with LangGraph to:
    - Persist multi-step conversation state
    - Resume from any checkpoint
    - Share context with Mem0 memories
    
    Usage:
        from mem0.langgraph_integration import Mem0CheckpointSaver
        from langgraph.graph import StateGraph
        
        saver = Mem0CheckpointSaver()
        graph = StateGraph(...)
        app = graph.compile(checkpointer=saver)
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        if not LANGGRAPH_AVAILABLE:
            raise ImportError(
                "LangGraph is not installed. Install with: pip install langgraph"
            )
        
        self.connection_string = connection_string or os.environ.get(
            "SUPABASE_CONNECTION_STRING",
            "postgresql://postgres:postgres@localhost:5432/postgres"
        )
        self.engine: Engine = create_engine(self.connection_string)
        self._ensure_table()
    
    def _ensure_table(self) -> None:
        """Create the checkpoints table if it doesn't exist."""
        with self.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS langgraph_checkpoints (
                    id SERIAL PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    parent_checkpoint_id TEXT,
                    checkpoint JSONB NOT NULL,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(thread_id, checkpoint_id)
                );
                CREATE INDEX IF NOT EXISTS idx_checkpoints_thread 
                ON langgraph_checkpoints(thread_id);
            """))
            conn.commit()
    
    def get(self, config: Dict[str, Any]) -> Optional[Checkpoint]:
        """Get the latest checkpoint for a thread."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return None
        
        with self.engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT checkpoint, checkpoint_id, parent_checkpoint_id
                    FROM langgraph_checkpoints
                    WHERE thread_id = :thread_id
                    ORDER BY created_at DESC
                    LIMIT 1
                """),
                {"thread_id": thread_id}
            ).fetchone()
            
            if result:
                return {
                    "v": 1,
                    "id": result[1],
                    "ts": datetime.now().isoformat(),
                    "channel_values": result[0],
                    "channel_versions": {},
                    "versions_seen": {},
                    "pending_sends": [],
                }
        return None
    
    def put(self, config: Dict[str, Any], checkpoint: Checkpoint, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Save a checkpoint."""
        thread_id = config.get("configurable", {}).get("thread_id")
        checkpoint_id = checkpoint.get("id", str(datetime.now().timestamp()))
        parent_id = config.get("configurable", {}).get("checkpoint_id")
        
        with self.engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO langgraph_checkpoints 
                    (thread_id, checkpoint_id, parent_checkpoint_id, checkpoint, metadata)
                    VALUES (:thread_id, :checkpoint_id, :parent_id, :checkpoint, :metadata)
                    ON CONFLICT (thread_id, checkpoint_id) 
                    DO UPDATE SET checkpoint = :checkpoint, metadata = :metadata
                """),
                {
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id,
                    "parent_id": parent_id,
                    "checkpoint": checkpoint.get("channel_values", {}),
                    "metadata": metadata
                }
            )
            conn.commit()
        
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id
            }
        }
    
    def list(self, config: Dict[str, Any], *, before: Optional[str] = None, limit: int = 10) -> List[Checkpoint]:
        """List checkpoints for a thread."""
        thread_id = config.get("configurable", {}).get("thread_id")
        
        with self.engine.connect() as conn:
            query = """
                SELECT checkpoint, checkpoint_id, created_at
                FROM langgraph_checkpoints
                WHERE thread_id = :thread_id
            """
            if before:
                query += " AND checkpoint_id < :before"
            query += " ORDER BY created_at DESC LIMIT :limit"
            
            results = conn.execute(
                text(query),
                {"thread_id": thread_id, "before": before, "limit": limit}
            ).fetchall()
            
            return [
                {
                    "v": 1,
                    "id": row[1],
                    "ts": row[2].isoformat() if row[2] else None,
                    "channel_values": row[0],
                }
                for row in results
            ]


# Convenience function to get a configured saver
def get_checkpoint_saver() -> Mem0CheckpointSaver:
    """
    Get a Mem0CheckpointSaver instance configured from environment.
    
    Returns:
        Mem0CheckpointSaver: Ready-to-use checkpoint saver
    """
    return Mem0CheckpointSaver()

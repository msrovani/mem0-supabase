import logging
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime

logger = logging.getLogger(__name__)


class PostgresManager:
    def __init__(self, connection_string: str):
        self.engine = create_engine(connection_string)
        self.Session = sessionmaker(bind=self.engine)
        self._ensure_table()

    def _ensure_table(self) -> None:
        """
        Create the history table if it doesn't exist.
        """
        with self.engine.connect() as conn:
            stmt = text("""
                CREATE TABLE IF NOT EXISTS history (
                    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    memory_id    TEXT,
                    old_memory   TEXT,
                    new_memory   TEXT,
                    event        TEXT,
                    created_at   TIMESTAMPTZ DEFAULT NOW(),
                    updated_at   TIMESTAMPTZ DEFAULT NOW(),
                    is_deleted   BOOLEAN DEFAULT FALSE,
                    actor_id     TEXT,
                    actor_type   TEXT,
                    role         TEXT,
                    user_id      TEXT,
                    conversation_id TEXT,
                    provenance   JSONB
                );
                CREATE INDEX IF NOT EXISTS idx_history_memory_id ON history(memory_id);
                CREATE INDEX IF NOT EXISTS idx_history_actor_id ON history(actor_id);
                CREATE INDEX IF NOT EXISTS idx_history_conversation_id ON history(conversation_id);
            """)
            conn.execute(stmt)
            conn.commit()

    def add_history(
        self,
        memory_id: str,
        old_memory: Optional[str],
        new_memory: Optional[str],
        event: str,
        *,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        is_deleted: int = 0,
        actor_id: Optional[str] = None,
        actor_type: Optional[str] = None,
        role: Optional[str] = None,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> None:
        session = self.Session()
        try:
            stmt = text("""
                INSERT INTO history (
                    id, memory_id, old_memory, new_memory, event,
                    created_at, updated_at, is_deleted, actor_id, actor_type, role, user_id,
                    conversation_id, provenance
                )
                VALUES (
                    :id, :memory_id, :old_memory, :new_memory, :event,
                    :created_at, :updated_at, :is_deleted, :actor_id, :actor_type, :role, :user_id,
                    :conversation_id, :provenance
                )
            """)

            # Use provided timestamps or default to now (Postgres handles defaults, but if None is passed explicitly as param logic might vary.
            # SQLiteManager passes None by default. Postgres DEFAULT NOW() handles None if we omit the column,
            # but here we are binding. Python None -> NULL in SQL.
            # If created_at is None, we want Postgres to use NOW().
            # Simplest for cross-db compatibility is to generate in Python if None.

            c_at = created_at if created_at else datetime.now()
            u_at = updated_at if updated_at else datetime.now()

            session.execute(
                stmt,
                {
                    "id": str(uuid.uuid4()),
                    "memory_id": memory_id,
                    "old_memory": old_memory,
                    "new_memory": new_memory,
                    "event": event,
                    "created_at": c_at,
                    "updated_at": u_at,
                    "is_deleted": bool(is_deleted),
                    "actor_id": actor_id,
                    "actor_type": actor_type,
                    "role": role,
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "provenance": provenance,
                },
            )
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to add history record (Postgres): {e}")
            raise
        finally:
            session.close()

    def get_history(self, memory_id: str) -> List[Dict[str, Any]]:
        session = self.Session()
        try:
            stmt = text("""
                SELECT id, memory_id, old_memory, new_memory, event,
                       created_at, updated_at, is_deleted, actor_id, actor_type, role, user_id,
                       conversation_id, provenance
                FROM history
                WHERE memory_id = :memory_id
                ORDER BY created_at ASC, updated_at ASC
            """)
            result = session.execute(stmt, {"memory_id": memory_id})
            rows = result.fetchall()

            return [
                {
                    "id": str(row.id),
                    "memory_id": row.memory_id,
                    "old_memory": row.old_memory,
                    "new_memory": row.new_memory,
                    "event": row.event,
                    "created_at": str(row.created_at) if row.created_at else None,
                    "updated_at": str(row.updated_at) if row.updated_at else None,
                    "is_deleted": row.is_deleted,
                    "actor_id": row.actor_id,
                    "actor_type": row.actor_type,
                    "role": row.role,
                    "user_id": row.user_id,
                    "conversation_id": row.conversation_id,
                    "provenance": row.provenance,
                }
                for row in rows
            ]
        finally:
            session.close()

    def reset(self) -> None:
        """Drop and recreate the history table."""
        with self.engine.connect() as conn:
            try:
                conn.execute(text("DROP TABLE IF EXISTS history"))
                conn.commit()
                self._ensure_table()
            except Exception as e:
                logger.error(f"Failed to reset history table (Postgres): {e}")
                raise

    def close(self) -> None:
        pass  # SQLAlchemy engine manages connections

    # =========================================================================
    # Actor-Aware Memory Queries (Phase 1.2)
    # Origin: Mem0 Group-Chat v2 (PR #2669)
    # =========================================================================

    def get_by_actor(self, actor_id: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all history records for a specific actor."""
        session = self.Session()
        try:
            stmt = text("""
                SELECT id, memory_id, old_memory, new_memory, event,
                       created_at, updated_at, is_deleted, actor_id, actor_type, role, user_id,
                       conversation_id, provenance
                FROM history
                WHERE actor_id = :actor_id
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """)
            result = session.execute(stmt, {"actor_id": actor_id, "limit": limit, "offset": offset})
            rows = result.fetchall()

            return [
                {
                    "id": str(row.id),
                    "memory_id": row.memory_id,
                    "old_memory": row.old_memory,
                    "new_memory": row.new_memory,
                    "event": row.event,
                    "created_at": str(row.created_at) if row.created_at else None,
                    "updated_at": str(row.updated_at) if row.updated_at else None,
                    "is_deleted": row.is_deleted,
                    "actor_id": row.actor_id,
                    "actor_type": row.actor_type,
                    "role": row.role,
                    "user_id": row.user_id,
                    "conversation_id": row.conversation_id,
                    "provenance": row.provenance,
                }
                for row in rows
            ]
        finally:
            session.close()

    def get_by_conversation(self, conversation_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get all history records for a specific conversation."""
        session = self.Session()
        try:
            stmt = text("""
                SELECT id, memory_id, old_memory, new_memory, event,
                       created_at, updated_at, is_deleted, actor_id, actor_type, role, user_id,
                       conversation_id, provenance
                FROM history
                WHERE conversation_id = :conversation_id
                ORDER BY created_at ASC
                LIMIT :limit
            """)
            result = session.execute(stmt, {"conversation_id": conversation_id, "limit": limit})
            rows = result.fetchall()

            return [
                {
                    "id": str(row.id),
                    "memory_id": row.memory_id,
                    "old_memory": row.old_memory,
                    "new_memory": row.new_memory,
                    "event": row.event,
                    "created_at": str(row.created_at) if row.created_at else None,
                    "updated_at": str(row.updated_at) if row.updated_at else None,
                    "is_deleted": row.is_deleted,
                    "actor_id": row.actor_id,
                    "actor_type": row.actor_type,
                    "role": row.role,
                    "user_id": row.user_id,
                    "conversation_id": row.conversation_id,
                    "provenance": row.provenance,
                }
                for row in rows
            ]
        finally:
            session.close()

    def get_by_actor_and_conversation(
        self, actor_id: str, conversation_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get history records for a specific actor within a specific conversation."""
        session = self.Session()
        try:
            stmt = text("""
                SELECT id, memory_id, old_memory, new_memory, event,
                       created_at, updated_at, is_deleted, actor_id, actor_type, role, user_id,
                       conversation_id, provenance
                FROM history
                WHERE actor_id = :actor_id AND conversation_id = :conversation_id
                ORDER BY created_at ASC
                LIMIT :limit
            """)
            result = session.execute(stmt, {"actor_id": actor_id, "conversation_id": conversation_id, "limit": limit})
            rows = result.fetchall()

            return [
                {
                    "id": str(row.id),
                    "memory_id": row.memory_id,
                    "old_memory": row.old_memory,
                    "new_memory": row.new_memory,
                    "event": row.event,
                    "created_at": str(row.created_at) if row.created_at else None,
                    "updated_at": str(row.updated_at) if row.updated_at else None,
                    "is_deleted": row.is_deleted,
                    "actor_id": row.actor_id,
                    "actor_type": row.actor_type,
                    "role": row.role,
                    "user_id": row.user_id,
                    "conversation_id": row.conversation_id,
                    "provenance": row.provenance,
                }
                for row in rows
            ]
        finally:
            session.close()

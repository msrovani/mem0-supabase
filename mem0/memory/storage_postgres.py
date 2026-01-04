import logging
import uuid
import os
from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine, text, Column, String, DateTime, Integer, Boolean, MetaData, Table, inspect
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
                    role         TEXT,
                    user_id      TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_history_memory_id ON history(memory_id);
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
        role: Optional[str] = None,
    ) -> None:
        session = self.Session()
        try:
            stmt = text("""
                INSERT INTO history (
                    id, memory_id, old_memory, new_memory, event,
                    created_at, updated_at, is_deleted, actor_id, role
                )
                VALUES (
                    :id, :memory_id, :old_memory, :new_memory, :event,
                    :created_at, :updated_at, :is_deleted, :actor_id, :role
                )
            """)
            
            # Use provided timestamps or default to now (Postgres handles defaults, but if None is passed explicitly as param logic might vary. 
            # SQLiteManager passes None by default. Postgres DEFAULT NOW() handles None if we omit the column, 
            # but here we are binding. Python None -> NULL in SQL.
            # If created_at is None, we want Postgres to use NOW().
            # Simplest for cross-db compatibility is to generate in Python if None.
            
            c_at = created_at if created_at else datetime.now()
            u_at = updated_at if updated_at else datetime.now()

            session.execute(stmt, {
                "id": str(uuid.uuid4()),
                "memory_id": memory_id,
                "old_memory": old_memory,
                "new_memory": new_memory,
                "event": event,
                "created_at": c_at,
                "updated_at": u_at,
                "is_deleted": bool(is_deleted),
                "actor_id": actor_id,
                "role": role
            })
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
                       created_at, updated_at, is_deleted, actor_id, role
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
                    "role": row.role,
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

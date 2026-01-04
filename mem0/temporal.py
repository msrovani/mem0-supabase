import logging
import pytz
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import text
from mem0.memory.base_supabase import SupabaseManager
from mem0.exceptions import DatabaseError

class TemporalMemory(SupabaseManager):
    """
    Provides time-travel memory queries and version tracking for Mem0-Supabase.
    
    This module enables agents to query historical states of their knowledge,
    track the evolution of specific memories, and perform time-based comparisons.
    """
    
    def get_memories_at(
        self, 
        user_id: str, 
        at_time: Optional[datetime] = None,
        days_ago: Optional[int] = None,
        hours_ago: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves memories as they existed at a specific point in time.
        
        Args:
            user_id: The ID of the user whose memories to retrieve.
            at_time: Specific datetime to query (defaults to UTC now).
            days_ago: Optional offset in days from current time.
            hours_ago: Optional offset in hours from current time.
            
        Returns:
            A list of memories valid at the calculated target timestamp.
            
        Raises:
            DatabaseError: If the temporal query fails.
        """
        now = datetime.now(pytz.utc)
        if at_time:
            target_time = at_time
            if target_time.tzinfo is None:
                target_time = pytz.utc.localize(target_time)
        elif days_ago:
            target_time = now - timedelta(days=days_ago)
        elif hours_ago:
            target_time = now - timedelta(hours=hours_ago)
        else:
            target_time = now
        
        self.logger.info(f"Querying memories for user {user_id} at {target_time.isoformat()}")
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text(f"""
                        SELECT 
                            id,
                            metadata->>'data' as content,
                            metadata,
                            memory_type,
                            valid_from,
                            valid_to,
                            is_current
                        FROM {self.table_name}
                        WHERE (metadata->>'user_id' = :user_id OR metadata->>'user_id' IS NULL)
                          AND valid_from <= :target_time
                          AND valid_to > :target_time
                        ORDER BY valid_from DESC
                    """),
                    {"user_id": user_id, "target_time": target_time}
                ).fetchall()
                
                return [
                    {
                        "id": str(row[0]),
                        "content": row[1],
                        "metadata": row[2],
                        "memory_type": row[3],
                        "valid_from": row[4].isoformat() if row[4] else None,
                        "valid_to": row[5].isoformat() if row[5] else None,
                        "is_current": row[6]
                    }
                    for row in result
                ]
        except Exception as e:
            self.logger.error(f"Temporal query failed: {str(e)}")
            raise DatabaseError(message=f"Failed to retrieve temporal memories: {str(e)}")
    
    def get_memory_history(self, memory_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves the complete version history (audit trail) of a specific memory.
        
        Args:
            memory_id: UUID of any version of the memory.
            
        Returns:
            A list of all versions ordered chronologically.
            
        Raises:
            DatabaseError: If the history chain retrieval fails.
        """
        self.logger.info(f"Retrieving version history for memory {memory_id}")
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text(f"""
                        WITH memory_chain AS (
                            SELECT (metadata->>'original_id')::uuid as original_id
                            FROM {self.table_name} 
                            WHERE id = :memory_id
                        )
                        SELECT 
                            m.id,
                            m.metadata->>'data' as content,
                            m.valid_from,
                            m.valid_to,
                            m.is_current,
                            m.memory_type
                        FROM {self.table_name} m
                        WHERE m.id = :memory_id
                           OR m.id = (SELECT original_id FROM memory_chain)
                           OR (m.metadata->>'original_id')::uuid = (SELECT original_id FROM memory_chain)
                        ORDER BY m.valid_from ASC
                    """),
                    {"memory_id": memory_id}
                ).fetchall()
                
                return [
                    {
                        "id": str(row[0]),
                        "content": row[1],
                        "valid_from": row[2].isoformat() if row[2] else None,
                        "valid_to": row[3].isoformat() if row[3] else None,
                        "is_current": row[4],
                        "memory_type": row[5]
                    }
                    for row in result
                ]
        except Exception as e:
            raise DatabaseError(message=f"Failed to fetch memory history: {str(e)}")
    
    def compare_memory_states(
        self, 
        user_id: str, 
        time1: datetime, 
        time2: datetime
    ) -> Dict[str, Any]:
        """
        Performs a logical diff between the memory states at two points in time.
        
        Args:
            user_id: User ID to compare.
            time1: Baseline timestamp.
            time2: Target timestamp for comparison.
            
        Returns:
            A comparison report dict with added, removed, and metadata.
        """
        self.logger.info(f"Comparing memory states for user {user_id} between {time1} and {time2}")
        
        memories_t1 = {m["content"]: m for m in self.get_memories_at(user_id, at_time=time1)}
        memories_t2 = {m["content"]: m for m in self.get_memories_at(user_id, at_time=time2)}
        
        t1_contents = set(memories_t1.keys())
        t2_contents = set(memories_t2.keys())
        
        added = t2_contents - t1_contents
        removed = t1_contents - t2_contents
        
        return {
            "time1": time1.isoformat(),
            "time2": time2.isoformat(),
            "added": [memories_t2[c] for c in added],
            "removed": [memories_t1[c] for c in removed],
            "unchanged_count": len(t1_contents & t2_contents),
            "total_t1": len(t1_contents),
            "total_t2": len(t2_contents)
        }
    
    def get_memory_timeline(
        self, 
        user_id: str, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Returns a simplified event timeline of memory mutations.
        
        Args:
            user_id: Target user ID.
            start_date: Timeline start (defaults to 30 days ago).
            end_date: Timeline end (defaults to now).
            limit: Maximum number of events to return.
            
        Returns:
            A list of mutation events (active, expired, superseded).
        """
        start = start_date or (datetime.now() - timedelta(days=30))
        end = end_date or datetime.now()
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text(f"""
                        SELECT 
                            id,
                            metadata->>'data' as content,
                            memory_type,
                            valid_from,
                            valid_to,
                            is_current,
                            CASE 
                                WHEN valid_to < :end_date AND valid_to != 'infinity' THEN 'expired'
                                WHEN NOT is_current THEN 'superseded'
                                ELSE 'active'
                            END as status
                        FROM {self.table_name}
                        WHERE metadata->>'user_id' = :user_id
                          AND valid_from BETWEEN :start_date AND :end_date
                        ORDER BY valid_from DESC
                        LIMIT :limit
                    """),
                    {
                        "user_id": user_id,
                        "start_date": start,
                        "end_date": end,
                        "limit": limit
                    }
                ).fetchall()
                
                return [
                    {
                        "id": str(row[0]),
                        "content": row[1][:100] + "..." if len(row[1] or "") > 100 else row[1],
                        "memory_type": row[2],
                        "valid_from": row[3].isoformat() if row[3] else None,
                        "valid_to": row[4].isoformat() if row[4] else None,
                        "is_current": row[5],
                        "status": row[6]
                    }
                    for row in result
                ]
        except Exception as e:
            raise DatabaseError(message=f"Failed to generate timeline: {str(e)}")

def time_travel(user_id: str, days_ago: int = 7) -> List[Dict[str, Any]]:
    """
    Shortcut helper to retrieve memories from a specific point in history.
    """
    tm = TemporalMemory()
    return tm.get_memories_at(user_id, days_ago=days_ago)

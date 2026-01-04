import logging
from typing import Optional, List, Dict, Any
from sqlalchemy import text
from mem0.memory.base_supabase import SupabaseManager
from mem0.exceptions import DatabaseError

class LifecycleManager(SupabaseManager):
    """
    Unified manager for Memory Durability and Archiving in Mem0-Supabase.
    
    This class manages the "Forgetting Curve" logic, importance scoring,
    and archival states, ensuring agent context remains relevant and clean.
    """
    
    def update_access(self, memory_id: str) -> None:
        """
        Registers a memory access event, resetting the decay timer and boosting importance.
        
        Args:
            memory_id: The UUID of the memory being accessed.
            
        Raises:
            DatabaseError: If the update operation fails in Supabase.
        """
        self.logger.debug(f"Updating access for memory_id: {memory_id}")
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    text(f"""
                        UPDATE {self.table_name} 
                        SET last_accessed_at = NOW(),
                            importance_score = LEAST(1.0, importance_score + 0.1)
                        WHERE id = :memory_id
                    """),
                    {"memory_id": memory_id}
                )
                conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to update access for memory {memory_id}: {str(e)}")
            raise DatabaseError(
                message=f"Could not update access for memory {memory_id}",
                details={"memory_id": memory_id, "error": str(e)},
                suggestion="Check your Supabase connection and ensure the table schema is correct."
            )

    def get_decay_stats(self, user_id: str) -> Dict[str, int]:
        """
        Retrieves statistics about memory distribution by importance levels for a user.
        
        Args:
            user_id: The ID of the user whose memory stats are being retrieved.
            
        Returns:
            A dictionary containing counts for 'high', 'medium', and 'near_archival' memories.
            
        Raises:
            DatabaseError: If the analytical query fails.
        """
        self.logger.info(f"Retrieving decay stats for user_id: {user_id}")
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text(f"""
                        SELECT 
                            count(*) filter (where importance_score > 0.8) as high,
                            count(*) filter (where importance_score <= 0.8 and importance_score > 0.2) as medium,
                            count(*) filter (where importance_score <= 0.2) as near_archival
                        FROM {self.table_name}
                        WHERE metadata->>'user_id' = :user_id 
                          AND is_current = TRUE
                    """),
                    {"user_id": user_id}
                ).fetchone()
                
                return {
                    "high_importance": int(result[0] or 0),
                    "medium_importance": int(result[1] or 0),
                    "near_archival": int(result[2] or 0)
                }
        except Exception as e:
            self.logger.error(f"Failed to get decay stats for user {user_id}: {str(e)}")
            raise DatabaseError(
                message="Could not retrieve memory decay statistics",
                details={"user_id": user_id, "error": str(e)}
            )

    def set_importance(self, memory_id: str, score: float) -> None:
        """
        Manually sets the importance score for a memory (e.g., pinning).
        
        Args:
            memory_id: The UUID of the memory to update.
            score: The importance score to set (clamped between 0.0 and 1.0).
            
        Raises:
            DatabaseError: If the update fails.
        """
        score = max(0.0, min(1.0, score))
        self.logger.info(f"Setting importance for memory {memory_id} to {score}")
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    text(f"UPDATE {self.table_name} SET importance_score = :score WHERE id = :id"),
                    {"score": score, "id": memory_id}
                )
                conn.commit()
        except Exception as e:
            raise DatabaseError(message=f"Failed to set importance: {str(e)}")

    def trigger_batch_decay(self) -> None:
        """
        Triggers the scheduled importance decay process manually.
        
        Raises:
            DatabaseError: If the SQL function call fails.
        """
        self.logger.warning("Triggering manual batch decay process")
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT decay_memory_importance()"))
                conn.commit()
        except Exception as e:
            raise DatabaseError(message=f"Batch decay trigger failed: {str(e)}")

def refresh_memory(memory_id: str) -> None:
    """
    Convenience function to refresh a memory's lifecycle state standalone.
    
    Args:
        memory_id: The UUID of the memory.
    """
    lm = LifecycleManager()
    lm.update_access(memory_id)

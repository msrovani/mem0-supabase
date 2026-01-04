import os
import logging
from typing import Optional
from sqlalchemy import create_engine, Engine
from mem0.exceptions import ConfigurationError

class SupabaseManager:
    """
    Base class for Supabase-related managers in Mem0.
    Handles engine initialization and environment variable validation.
    """
    
    def __init__(self, connection_string: Optional[str] = None, table_name: str = "memories"):
        self.logger = logging.getLogger(self.__class__.__module__)
        
        self.connection_string = connection_string or os.environ.get("SUPABASE_CONNECTION_STRING")
        if not self.connection_string:
            raise ConfigurationError(
                message="SUPABASE_CONNECTION_STRING is missing",
                error_code="CFG_002",
                suggestion="Please set the SUPABASE_CONNECTION_STRING environment variable or pass it to the constructor."
            )
            
        self.table_name = table_name
        self.engine: Engine = create_engine(self.connection_string, pool_pre_ping=True)
        self.logger.debug(f"Initialized {self.__class__.__name__} with table: {self.table_name}")

        # Supabase SDK Client for Realtime and Storage
        self.supabase_url = os.environ.get("SUPABASE_URL")
        self.supabase_key = os.environ.get("SUPABASE_KEY")
        self._client = None

    @property
    def client(self):
        """Lazy initialization of the Supabase client."""
        if self._client is None:
            if not self.supabase_url or not self.supabase_key:
                self.logger.warning("SUPABASE_URL or SUPABASE_KEY missing. Realtime features disabled.")
                return None
            try:
                from supabase import create_client, Client
                self._client = create_client(self.supabase_url, self.supabase_key)
            except ImportError:
                self.logger.error("The 'supabase' library is required for Realtime features.")
                return None
        return self._client

    def reinforce_memory(self, memory_id: str) -> None:
        """
        Increments the reinforcement count of a memory and updates its access time.
        This is part of the SSR 'Subconscious' processing.
        """
        from sqlalchemy import text
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    text(f"""
                        UPDATE {self.table_name} 
                        SET reinforcement_count = reinforcement_count + 1, 
                            updated_at = NOW(),
                            payload = jsonb_set(payload, '{{reinforcement_count}}', (reinforcement_count + 1)::text::jsonb)
                        WHERE id = :id
                    """),
                    {"id": memory_id}
                )
                conn.commit()
            self.logger.info(f"Memory {memory_id} reinforced (low surprise).")
        except Exception as e:
            self.logger.error(f"Failed to reinforce memory {memory_id}: {e}")

    def subscribe_to_resonance(self, callback) -> Optional[Any]:
        """
        Subscribes to the 'resonance' channel for real-time memory updates.
        This listener detects high-importance or flashbulb memories created by ANY agent.
        """
        if not self.client:
            return None

        def on_change(payload):
            # Extract cognitive markers
            is_flashbulb = payload.get("new", {}).get("is_flashbulb", False)
            importance = payload.get("new", {}).get("payload", {}).get("importance_score", 0.0)
            
            # Resonance condition: If it's a flashbulb OR very important (>0.8)
            if is_flashbulb or importance > 0.8:
                self.logger.debug(f"Resonance detected! Payload: {payload.get('new', {}).get('id')}")
                callback(payload.get("new"))

        channel = self.client.channel("resonance_layer")
        channel.on(
            "postgres_changes",
            {
                "event": "*",
                "schema": "vecs",
                "table": self.table_name
            },
            on_change
        ).subscribe()
        
        self.logger.info(f"Subscribed to synaptic resonance on table: {self.table_name}")
        return channel

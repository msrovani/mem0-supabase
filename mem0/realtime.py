import os
import asyncio
import logging
from typing import Callable, Optional
# Requires: pip install supabase
from supabase import create_client, Client

logger = logging.getLogger(__name__)

class RealtimeMemory:
    """
    Listens to changes in the Supabase 'memories' or 'history' table in real-time.
    Enable 'Reflexive Memory' patterns where an agent reacts to its own thoughts.
    """
    def __init__(self, check_env: bool = True):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
        
        if check_env and (not url or not key):
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY/ANON_KEY env vars required for Realtime.")
            
        self.supabase: Client = create_client(url, key)
        self.callbacks = []

    def on_memory_added(self, callback: Callable[[dict], None]):
        """Register a callback for when a new memory is added."""
        self.callbacks.append(callback)

    async def listen(self):
        """Start listening to the 'history' table inserts."""
        # Note: 'history' table must have Realtime enabled in Supabase Dashboard -> Database -> Replication.
        
        def _handler(payload):
            if payload.get("eventType") == "INSERT":
                record = payload.get("new")
                logger.info(f"New Memory Event received: {record.get('id')}")
                for cb in self.callbacks:
                    try:
                        cb(record)
                    except Exception as e:
                        logger.error(f"Error in callback: {e}")

        # Subscribe to 'history' table
        channel = self.supabase.table("history").on("INSERT", _handler).subscribe()
        logger.info("Listening for new memories on 'history' table...")
        
        # Keep alive - minimal implementation
        while True:
            await asyncio.sleep(1)

if __name__ == "__main__":
    # Example Usage: run this as a standalone worker "Reflexion Agent"
    async def main():
        client = RealtimeMemory(check_env=False) # Config check skipped for demo
        
        def reflect_on_memory(record):
            print(f"Reflecting on: {record}")
            # Here you would call LLM to analyze the memory and potentially add a new insight.
            
        client.on_memory_added(reflect_on_memory)
        await client.listen()

    # asyncio.run(main()) 

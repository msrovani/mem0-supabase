import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class MemoryBridge:
    """
    [Salto: Memory Bridge]
    Manages cross-agent memory synchronization with granular permissions.
    Allows agents to have "Private Memories" (specific to an agent) and 
    "Shared Memories" (accessible to all agents under a user/org).
    """

    def __init__(self, memory_instance):
        self.memory = memory_instance

    def get_context(self, user_id: str, agent_id: str) -> Dict[str, Any]:
        """
        Retrieves a combined context of Private (agent-specific) and Shared (user-wide) memories.
        """
        # 1. Fetch Shared Memories (no agent_id)
        shared_filters = {"user_id": user_id, "agent_id": None}
        
        # 2. Fetch Private Memories (specific to this agent)
        private_filters = {"user_id": user_id, "agent_id": agent_id}

        # We can use the memory instance to search/get_all
        # This is a conceptual implementation that would be called during 'recollect'
        return {
            "shared": shared_filters,
            "private": private_filters
        }

    def share_memory(self, memory_id: str, target_agent_ids: Optional[List[str]] = None):
        """
        Promotes a private memory to a shared one or shares it with specific agents.
        """
        try:
            memory = self.memory.get(memory_id)
            if not memory:
                return False
            
            # If target_agent_ids is None, make it global for the user (agent_id = None)
            new_agent_id = None if not target_agent_ids else target_agent_ids
            
            # Update the memory in the vector store
            # Note: This requires the memory instance to have an update method that handles agent_id
            self.memory.update(memory_id, data=memory["memory"], metadata={"agent_id": new_agent_id})
            logger.info(f"Memory {memory_id} shared with {new_agent_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to share memory: {e}")
            return False

    async def get_context_async(self, user_id: str, agent_id: str):
        import asyncio
        return await asyncio.to_thread(self.get_context, user_id, agent_id)

    async def share_memory_async(self, memory_id: str, target_agent_ids: Optional[List[str]] = None):
        import asyncio
        return await asyncio.to_thread(self.share_memory, memory_id, target_agent_ids)

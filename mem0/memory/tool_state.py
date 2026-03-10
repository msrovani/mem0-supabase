import logging
import json
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class ToolStateManager:
    """
    [Salto: Tool-State Memory]
    Manages the 'Save Game' for AI tools.
    Saves snapshots of tool states (e.g., open URLs, file cursors, active variables) 
    to Supabase for persistent, stateful tool use.
    """

    def __init__(self, vector_store=None):
        self.vector_store = vector_store

    def save_state(self, tool_id: str, state: Dict[str, Any], user_id: str, agent_id: Optional[str] = None):
        """
        Saves the current state of a tool.
        """
        if not self.vector_store:
            return None

        state_json = json.dumps(state)
        metadata = {
            "user_id": user_id,
            "agent_id": agent_id,
            "tool_id": tool_id,
            "memory_type": "tool_state",
            "updated_at": datetime.utcnow().isoformat(),
            "data": f"Tool State for {tool_id}: {state_json}"
        }

        # We use a unique ID for the tool-state to avoid duplication, or a deterministic one based on tool_id
        state_id = f"state_{tool_id}_{user_id}"
        if agent_id:
            state_id += f"_{agent_id}"
        
        # In Supabase, we can use update or insert
        # For simplicity, we'll use a fixed ID per tool/user/agent
        try:
            # We don't necessarily need a vector for state, but since we use a vector_store, 
            # we provide a dummy one if needed or just use the metadata store.
            dummy_vector = [0.0] * 1536 # Default size for many models
            self.vector_store.insert(vectors=[dummy_vector], ids=[state_id], payloads=[metadata])
            logger.info(f"Tool state saved for {tool_id} (user: {user_id})")
            return state_id
        except Exception as e:
            logger.error(f"Failed to save tool state: {e}")
            return None

    def get_state(self, tool_id: str, user_id: str, agent_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves the last saved state of a tool.
        """
        if not self.vector_store:
            return None

        state_id = f"state_{tool_id}_{user_id}"
        if agent_id:
            state_id += f"_{agent_id}"

        try:
            result = self.vector_store.get(vector_id=state_id)
            if result and result.payload:
                # The data is stored in the 'data' field, but the JSON is inside it
                raw_data = result.payload.get("data", "")
                if f"Tool State for {tool_id}: " in raw_data:
                    json_str = raw_data.replace(f"Tool State for {tool_id}: ", "")
                    return json.loads(json_str)
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve tool state: {e}")
            return None

    async def save_state_async(self, tool_id: str, state: Dict[str, Any], user_id: str, agent_id: Optional[str] = None):
        import asyncio
        return await asyncio.to_thread(self.save_state, tool_id, state, user_id, agent_id)

    async def get_state_async(self, tool_id: str, user_id: str, agent_id: Optional[str] = None):
        import asyncio
        return await asyncio.to_thread(self.get_state, tool_id, user_id, agent_id)

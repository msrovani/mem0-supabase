"""
CrewAI Integration — Mem0Memory for CrewAI agents.

Usage:
    from mem0.crewai_integration import Mem0Memory

    memory = Mem0Memory(
        base_url="http://localhost:8000",
        user_id="crew_user",
        api_key="your-jwt-token",
    )

    agent = Agent(
        role='Researcher',
        goal='Research topics',
        backstory='Expert researcher',
        memory=memory,
    )
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = ["Mem0Memory"]


class Mem0Memory:
    """
    CrewAI-compatible memory backend backed by Mem0.

    Stores agent interactions and retrieves relevant context
    for each agent turn.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.user_id = user_id
        self.agent_id = agent_id
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            from mem0.client import Mem0Client
            self._client = Mem0Client(base_url=self.base_url, api_key=self.api_key)
        return self._client

    def save(self, data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Save agent interaction to Mem0.

        Args:
            data: Dict with 'input' and/or 'output' keys.
            metadata: Additional metadata.
        """
        client = self._get_client()
        messages = []

        if "input" in data:
            messages.append({"role": "user", "content": str(data["input"])})
        if "output" in data:
            messages.append({"role": "assistant", "content": str(data["output"])})

        if messages:
            try:
                client.add(
                    messages,
                    user_id=self.user_id,
                    agent_id=self.agent_id,
                    metadata=metadata,
                )
            except Exception as e:
                logger.warning(f"Failed to save to Mem0: {e}")

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for relevant memories.

        Args:
            query: Search query.
            limit: Max results.

        Returns:
            List of memory dicts.
        """
        client = self._get_client()
        try:
            results = client.search(
                query,
                user_id=self.user_id,
                agent_id=self.agent_id,
            )
            return results.get("results", [])[:limit]
        except Exception as e:
            logger.warning(f"Failed to search Mem0: {e}")
            return []

    def reset(self) -> None:
        """Clear all memories for the current user."""
        client = self._get_client()
        try:
            client.delete_all(user_id=self.user_id, agent_id=self.agent_id)
        except Exception as e:
            logger.warning(f"Failed to reset Mem0: {e}")

"""
LangChain Integration — Mem0ChatMemory for LangChain agents.

Usage:
    from mem0.langchain_integration import Mem0ChatMemory

    memory = Mem0ChatMemory(
        base_url="http://localhost:8000",
        user_id="user1",
        api_key="your-jwt-token",
    )

    chain = LLMChain(llm=llm, memory=memory, prompt=prompt)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = ["Mem0ChatMemory"]


class Mem0ChatMemory:
    """
    LangChain-compatible chat memory backed by Mem0.

    Stores conversations in Mem0 and retrieves relevant context
    for each LLM call.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        api_key: Optional[str] = None,
        return_messages: bool = True,
        memory_key: str = "history",
        input_key: Optional[str] = None,
        output_key: Optional[str] = None,
    ):
        """
        Initialize Mem0ChatMemory.

        Args:
            base_url: Mem0 API base URL.
            user_id: User identifier for memory scoping.
            agent_id: Agent identifier.
            run_id: Run/session identifier.
            api_key: JWT token for authentication.
            return_messages: Return as message objects (True) or string (False).
            memory_key: Key for memory in chain output.
            input_key: Key for input in chain (optional).
            output_key: Key for output in chain (optional).
        """
        self.base_url = base_url.rstrip("/")
        self.user_id = user_id
        self.agent_id = agent_id
        self.run_id = run_id
        self.api_key = api_key
        self.return_messages = return_messages
        self.memory_key = memory_key
        self.input_key = input_key
        self.output_key = output_key

        # Lazy import to avoid hard dependency
        self._client = None

    def _get_client(self):
        """Lazy client initialization."""
        if self._client is None:
            from mem0.client import Mem0Client
            self._client = Mem0Client(
                base_url=self.base_url,
                api_key=self.api_key,
            )
        return self._client

    @property
    def memory_variables(self) -> List[str]:
        """Return memory variable names."""
        return [self.memory_key]

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Load memories relevant to the current input.

        Args:
            inputs: Chain input dict.

        Returns:
            Dict with memory key containing relevant memories.
        """
        client = self._get_client()

        # Get input text for context-aware retrieval
        input_text = ""
        if self.input_key and self.input_key in inputs:
            input_text = inputs[self.input_key]
        elif "input" in inputs:
            input_text = inputs["input"]

        # Search for relevant memories
        memories = []
        if input_text:
            try:
                result = client.search(
                    input_text,
                    user_id=self.user_id,
                    agent_id=self.agent_id,
                    run_id=self.run_id,
                )
                memories = result.get("results", [])
            except Exception as e:
                logger.warning(f"Failed to load memories: {e}")

        # Format as string or messages
        if self.return_messages:
            formatted = [
                {"role": "system", "content": m.get("memory", "")}
                for m in memories
            ]
        else:
            formatted = "\n".join(m.get("memory", "") for m in memories)

        return {self.memory_key: formatted}

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """
        Save conversation context to Mem0.

        Args:
            inputs: Chain input dict.
            outputs: Chain output dict.
        """
        client = self._get_client()

        # Extract input and output
        input_text = inputs.get(self.input_key or "input", "")
        output_text = outputs.get(self.output_key or "output", "")

        if not input_text and not output_text:
            return

        messages = []
        if input_text:
            messages.append({"role": "user", "content": str(input_text)})
        if output_text:
            messages.append({"role": "assistant", "content": str(output_text)})

        try:
            client.add(
                messages,
                user_id=self.user_id,
                agent_id=self.agent_id,
                run_id=self.run_id,
            )
        except Exception as e:
            logger.warning(f"Failed to save context: {e}")

    def clear(self) -> None:
        """Clear all memories for the current user."""
        client = self._get_client()
        try:
            client.delete_all(
                user_id=self.user_id,
                agent_id=self.agent_id,
                run_id=self.run_id,
            )
        except Exception as e:
            logger.warning(f"Failed to clear memories: {e}")

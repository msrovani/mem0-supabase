import logging
import json
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

REFLECTION_PROMPT = """
You are a meta-cognitive reflection engine. 
Review the following recent memories of an AI agent and identify:
1. **Contradictions**: Any new information that conflicts with previous beliefs.
2. **Patterns**: Recurring themes or preferences the agent should note.
3. **Identity Evolution**: How the agent's personality or values are changing.

Memories:
{memories}

Return a list of INSIGHTS to be added to the memory store.
Each insight should be a single, concise sentence.
"""

COMPACTION_PROMPT = """
You are a memory compaction engine. 
Below are many low-level interactions from a session. 
Rewrite them into 3 to 5 high-level PRINCIPLES or FACTS that summarize everything without losing the core intent.

Low-level memories:
{memories}

Return a JSON object: {{"compacted_memories": ["Fact 1", "Fact 2"]}}
"""

HEARTBEAT_PROMPT = """
You are a proactive agent heartbeat engine. 
Review the current context and determine if the agent should take an AUTONOMOUS action (Heartbeat).
(e.g., if a user said "remind me in 1 hour" and that time has passed, or if a task is pending).

Current Context:
{memories}

If an action is needed, return a concise suggestion. 
If not, return "NONE".
"""

class ReflectionEngine:
    """
    [Salto 3] Reflective Background Task.
    Performs self-correction, consolidates insights, agentic compaction, and proactivity (heartbeats).
    """

    def __init__(self, llm=None):
        self.llm = llm

    def _extract_text(self, memories: List[Dict[str, Any]]) -> str:
        memory_lines = []
        for m in memories:
            if isinstance(m, dict):
                text = m.get('memory') or m.get('text') or m.get('data') or str(m)
                memory_lines.append(f"- {text}")
            else:
                memory_lines.append(f"- {str(m)}")
        return "\n".join(memory_lines)

    def reflect(self, memories: List[Dict[str, Any]]) -> List[str]:
        """
        Analyzes memories for contradictions and patterns.
        """
        if not memories or not self.llm:
            return []

        logger.info(f"Reflection Engine: Analyzing {len(memories)} memories.")
        memory_text = self._extract_text(memories)
        prompt = REFLECTION_PROMPT.format(memories=memory_text)

        try:
            response = self.llm.generate_response(messages=[{"role": "user", "content": prompt}])
            insights = [line.strip("- ").strip() for line in response.split("\n") if line.strip()]
            return [i for i in insights if i]
        except Exception as e:
            logger.error(f"Reflection cycle failed: {e}")
            return []

    def compact(self, memories: List[Dict[str, Any]]) -> List[str]:
        """
        [Salto: Agentic Compaction]
        Rewrites many memories into a few high-level principles.
        """
        if not memories or not self.llm:
            return []

        logger.info(f"Compaction Engine: Compacting {len(memories)} memories.")
        memory_text = self._extract_text(memories)
        prompt = COMPACTION_PROMPT.format(memories=memory_text)

        try:
            from mem0.memory.utils import remove_code_blocks
            response = self.llm.generate_response(
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            data = json.loads(remove_code_blocks(response))
            return data.get("compacted_memories", [])
        except Exception as e:
            logger.error(f"Compaction failed: {e}")
            return []

    def generate_heartbeat(self, context: List[Dict[str, Any]]) -> Optional[str]:
        """
        [Salto: Proactive Heartbeats]
        Checks if the agent should take an autonomous action.
        """
        if not context or not self.llm:
            return None

        memory_text = self._extract_text(context)
        prompt = HEARTBEAT_PROMPT.format(memories=memory_text)

        try:
            response = self.llm.generate_response(messages=[{"role": "user", "content": prompt}]).strip()
            return None if response.upper() == "NONE" else response
        except Exception as e:
            logger.error(f"Heartbeat generation failed: {e}")
            return None

    async def reflect_async(self, memories: List[Dict[str, Any]]) -> List[str]:
        import asyncio
        return await asyncio.to_thread(self.reflect, memories)

    async def compact_async(self, memories: List[Dict[str, Any]]) -> List[str]:
        import asyncio
        return await asyncio.to_thread(self.compact, memories)

    async def generate_heartbeat_async(self, context: List[Dict[str, Any]]) -> Optional[str]:
        import asyncio
        return await asyncio.to_thread(self.generate_heartbeat, context)

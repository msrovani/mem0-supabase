import logging
import json
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

DREAM_PROMPT = """
You are a cognitive dreaming engine for an AI assistant.
Your task is to review the following memories and generate "SYNTHETIC MEMORIES" (insights reached through logic, not direct user input).

Cross-reference these memories to find hidden connections:
{memories}

Look for:
1. **Implied Preferences**: (e.g., if they like spicy food and Japan, they might like Wasabi).
2. **Behavioral Tendencies**: (e.g., if they code at 2 AM, they might be night owls).
3. **Implicit Goals**: (e.g., if they mention Python, Rust, and AI, they might be building a high-performance AI system).

Return a JSON object with a list of "synthetic_memories".
Format: {{"synthetic_memories": ["Insight 1", "Insight 2"]}}
Each synthetic memory must be a concise, factual-sounding sentence.
"""


class DreamingEngine:
    """
    [Salto: Dreaming Mode]
    Generates synthetic memories (conclusions reached by the AI) by cross-referencing existing data.
    """

    def __init__(self, llm=None):
        self.llm = llm

    def dream(self, memories: List[Dict[str, Any]]) -> List[str]:
        """
        Cross-references memories to generate synthetic insights.
        """
        if not memories or not self.llm:
            return []

        logger.info(f"Dreaming Engine: Processing {len(memories)} memories for cross-pollination.")

        # Extract text from memories
        memory_lines = []
        for m in memories:
            if isinstance(m, dict):
                text = m.get("memory") or m.get("text") or m.get("data") or str(m)
                memory_lines.append(f"- {text}")
            else:
                memory_lines.append(f"- {str(m)}")

        memory_text = "\n".join(memory_lines)
        prompt = DREAM_PROMPT.format(memories=memory_text)

        try:
            response = self.llm.generate_response(
                messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"}
            )
            from mem0.memory.utils import remove_code_blocks

            data = json.loads(remove_code_blocks(response))
            insights = data.get("synthetic_memories", [])
            logger.info(f"Dreaming completed: {len(insights)} synthetic memories generated.")
            return [i for i in insights if i]
        except Exception as e:
            logger.error(f"Dreaming cycle failed: {e}")
            return []

    async def dream_async(self, memories: List[Dict[str, Any]]) -> List[str]:
        """
        Asynchronous dreaming.
        """
        import asyncio

        return await asyncio.to_thread(self.dream, memories)

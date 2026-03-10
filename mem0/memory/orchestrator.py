import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

ORCHESTRATOR_PAGING_PROMPT = """
You are a context compression engine (Context Paging). 
You are given a list of memories that exceed the agent's current focus limit.
Your task is to summarize these "paged-out" memories into a single, high-density background context.

Paged-out Memories:
{paged_out_memories}

Instructions:
1. Extract only the critical facts and long-term context.
2. Maintain a chronological or logical flow.
3. Be extremadamente conciso (máximo 1 parágrafo).

Summary of Background Context:
"""


class ContextOrchestrator:
    """
    [Salto 2] Context Orchestrator (Paging Mechanism).
    Manages the 'RAM' (Active Context) and 'Disk' (Long-term Storage) trade-off.
    """

    def __init__(self, limit: int = 10, llm=None):
        self.limit = limit
        self.llm = llm

    def orchestrate(self, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Orchestrates memories by paging out those beyond the limit.
        """
        if not memories or len(memories) <= self.limit:
            return {"active_context": memories, "background_context": None}

        # Divide into Active (most recent/important) and Paged-out
        # In mem0, memories are usually already ranked by similarity/importance
        active = memories[: self.limit]
        paged_out = memories[self.limit :]

        logger.info(f"Context Orchestrator: Paging out {len(paged_out)} memories.")

        if not self.llm:
            return {"active_context": active, "background_context": f"Summarized {len(paged_out)} older items."}

        # Format paged-out memories for summarization
        paged_text = "\n".join([f"- {m.get('memory', m.get('text', ''))}" for m in paged_out])

        prompt = ORCHESTRATOR_PAGING_PROMPT.format(paged_out_memories=paged_text)

        try:
            summary = self.llm.generate_response(messages=[{"role": "user", "content": prompt}])
            return {"active_context": active, "background_context": summary.strip()}
        except Exception as e:
            logger.error(f"Paging orchestration failed: {e}")
            return {"active_context": active, "background_context": "Paging error."}

    async def orchestrate_async(self, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Asynchronous version of orchestrate.
        """
        import asyncio

        if not memories or len(memories) <= self.limit:
            return {"active_context": memories, "background_context": None}

        active = memories[: self.limit]
        paged_out = memories[self.limit :]

        logger.info(f"Context Orchestrator (Async): Paging out {len(paged_out)} memories.")

        if not self.llm:
            return {"active_context": active, "background_context": f"Summarized {len(paged_out)} older items."}

        paged_text = "\n".join([f"- {m.get('memory', m.get('text', ''))}" for m in paged_out])
        prompt = ORCHESTRATOR_PAGING_PROMPT.format(paged_out_memories=paged_text)

        try:
            summary = await asyncio.to_thread(
                self.llm.generate_response, messages=[{"role": "user", "content": prompt}]
            )
            return {"active_context": active, "background_context": summary.strip()}
        except Exception as e:
            logger.error(f"Async Paging orchestration failed: {e}")
            return {"active_context": active, "background_context": "Paging error."}

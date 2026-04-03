"""
SimpleMem Lifelong Memory - Phase 4.2
Origin: arXiv:2601.02553 - SimpleMem: Efficient Lifelong Memory for LLM Agents
        https://github.com/aiming-lab/SimpleMem

This module implements lifelong memory capabilities inspired by SimpleMem:
1. Online Semantic Synthesis - Merge new info with existing memories
2. Intent-Aware Retrieval Planning - Plan retrieval based on user intent
3. Memory Consolidation - Periodically consolidate old + new memories

Key insight: Avoid catastrophic forgetting by maintaining a balance
between new memory integration and old memory preservation.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SynthesisResult:
    """Result of semantic synthesis."""

    merged_memory: str
    source_memories: List[str]  # IDs of memories that were merged
    confidence: float
    is_new_fact: bool  # True if the result contains genuinely new information
    timestamp: str


@dataclass
class RetrievalPlan:
    """A plan for retrieving memories based on intent."""

    primary_memories: List[Dict[str, Any]]  # Most relevant
    secondary_memories: List[Dict[str, Any]]  # Contextual/background
    excluded_memories: List[str]  # IDs to explicitly exclude
    reasoning: str
    estimated_token_count: int


class SimpleMemLifelong:
    """
    Lifelong memory management inspired by SimpleMem.

    Usage:
        lifelong = SimpleMemLifelong(llm_client)
        result = lifelong.synthesize_memories("New fact", existing_memories)
        plan = lifelong.plan_retrieval("user query", context)
    """

    def __init__(self, llm_client: Any = None):
        self.llm_client = llm_client
        self._synthesis_history: List[SynthesisResult] = []

    def synthesize_memories(
        self,
        new_memory: str,
        existing_memories: List[Dict[str, Any]],
        similarity_threshold: float = 0.7,
    ) -> SynthesisResult:
        """
        Synthesize a new memory with existing similar memories.
        Inspired by SimpleMem's Online Semantic Synthesis.

        Args:
            new_memory: The new memory to synthesize
            existing_memories: Existing memories to potentially merge with
            similarity_threshold: Minimum similarity to consider merging

        Returns:
            SynthesisResult with merged memory or original if no merge needed
        """
        # Find similar existing memories
        similar = self._find_similar_memories(new_memory, existing_memories, similarity_threshold)

        if not similar:
            # No similar memories, store as-is
            result = SynthesisResult(
                merged_memory=new_memory,
                source_memories=[],
                confidence=1.0,
                is_new_fact=True,
                timestamp=datetime.now().isoformat(),
            )
        else:
            # Merge with similar memories
            source_ids = [m.get("id", "unknown") for m in similar]
            source_texts = [m.get("memory", "") for m in similar]

            if self.llm_client:
                merged = self._llm_merge(new_memory, source_texts)
            else:
                merged = self._rule_based_merge(new_memory, source_texts)

            result = SynthesisResult(
                merged_memory=merged,
                source_memories=source_ids,
                confidence=0.8,
                is_new_fact=False,
                timestamp=datetime.now().isoformat(),
            )

        self._synthesis_history.append(result)
        return result

    def plan_retrieval(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        max_tokens: int = 2000,
    ) -> RetrievalPlan:
        """
        Plan retrieval based on user intent.
        Inspired by SimpleMem's Intent-Aware Retrieval Planning.

        Args:
            query: The user's query
            context: Additional context (user_id, session, task type)
            max_tokens: Maximum token budget for retrieved memories

        Returns:
            RetrievalPlan with primary and secondary memories
        """
        context = context or {}
        intent = self._infer_intent(query, context)

        # Primary: Directly relevant memories
        primary = self._select_primary_memories(intent, query, max_tokens * 0.7)

        # Secondary: Contextual/background memories
        remaining_tokens = max_tokens - self._estimate_tokens(primary)
        secondary = self._select_secondary_memories(intent, context, remaining_tokens)

        # Exclude: Stale or contradicted memories
        excluded = self._get_excluded_memories(context)

        plan = RetrievalPlan(
            primary_memories=primary,
            secondary_memories=secondary,
            excluded_memories=excluded,
            reasoning=f"Intent: {intent}, Budget: {max_tokens} tokens",
            estimated_token_count=self._estimate_tokens(primary) + self._estimate_tokens(secondary),
        )

        return plan

    def consolidate(
        self,
        old_memories: List[Dict[str, Any]],
        new_memories: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Consolidate old and new memories, preserving important old memories
        while integrating new information.
        Inspired by SimpleMem's memory consolidation.

        Args:
            old_memories: Existing memories
            new_memories: Newly acquired memories

        Returns:
            Consolidated memory list
        """
        # Score each memory by importance
        old_scored = [(m, self._score_importance(m, is_old=True)) for m in old_memories]
        new_scored = [(m, self._score_importance(m, is_old=False)) for m in new_memories]

        # Keep high-importance old memories
        kept_old = [m for m, score in old_scored if score >= 0.5]

        # Keep all new memories (they're fresh)
        kept_new = [m for m, _ in new_scored]

        # Merge overlapping memories
        consolidated = list(kept_old)
        for new_mem in kept_new:
            similar = self._find_similar_memories(new_mem.get("memory", ""), consolidated, 0.8)
            if similar:
                # Merge
                result = self.synthesize_memories(
                    new_mem.get("memory", ""),
                    similar,
                )
                # Replace the similar memory with merged version
                for i, old in enumerate(consolidated):
                    if old.get("id") in result.source_memories:
                        consolidated[i] = {**old, "memory": result.merged_memory}
            else:
                consolidated.append(new_mem)

        logger.info(f"Consolidated: {len(old_memories)} old + {len(new_memories)} new -> {len(consolidated)} total")
        return consolidated

    def _find_similar_memories(
        self,
        text: str,
        memories: List[Dict[str, Any]],
        threshold: float,
    ) -> List[Dict[str, Any]]:
        """Find memories similar to the given text."""
        # Simple keyword-based similarity (replace with embedding-based in production)
        text_words = set(text.lower().split())
        similar = []

        for mem in memories:
            mem_text = mem.get("memory", "").lower()
            mem_words = set(mem_text.split())
            if not mem_words:
                continue

            overlap = len(text_words & mem_words)
            union = len(text_words | mem_words)
            similarity = overlap / union if union > 0 else 0.0

            if similarity >= threshold:
                similar.append(mem)

        return similar

    def _llm_merge(self, new_memory: str, existing_texts: List[str]) -> str:
        """Merge memories using LLM."""
        existing_str = "\n".join(f"- {t}" for t in existing_texts)
        prompt = f"""Merge the following memories into a single coherent memory.
Preserve all unique facts. Remove redundancies.

Existing memories:
{existing_str}

New memory:
{new_memory}

Merged memory:"""

        try:
            return self.llm_client.generate(prompt)
        except Exception as e:
            logger.error(f"LLM merge failed: {e}")
            return self._rule_based_merge(new_memory, existing_texts)

    def _rule_based_merge(self, new_memory: str, existing_texts: List[str]) -> str:
        """Merge memories without LLM (fallback)."""
        all_texts = existing_texts + [new_memory]
        # Simple deduplication: keep all unique sentences
        sentences = set()
        for text in all_texts:
            for sent in text.split(". "):
                sent = sent.strip()
                if sent:
                    sentences.add(sent)
        return ". ".join(sorted(sentences)) + "."

    def _infer_intent(self, query: str, context: Dict[str, Any]) -> str:
        """Infer the user's intent from the query."""
        query_lower = query.lower()

        if any(w in query_lower for w in ["how", "steps", "process", "way"]):
            return "procedural"
        elif any(w in query_lower for w in ["what", "who", "when", "where"]):
            return "factual"
        elif any(w in query_lower for w in ["why", "reason", "because"]):
            return "explanatory"
        elif any(w in query_lower for w in ["compare", "difference", "vs"]):
            return "comparative"
        elif any(w in query_lower for w in ["remember", "recall", "before"]):
            return "episodic"
        else:
            return "general"

    def _select_primary_memories(self, intent: str, query: str, token_budget: float) -> List[Dict[str, Any]]:
        """Select primary memories based on intent."""
        # Placeholder: in production, this would query the vector store
        return []

    def _select_secondary_memories(
        self, intent: str, context: Dict[str, Any], token_budget: float
    ) -> List[Dict[str, Any]]:
        """Select secondary/contextual memories."""
        return []

    def _get_excluded_memories(self, context: Dict[str, Any]) -> List[str]:
        """Get memory IDs to exclude from retrieval."""
        return []

    def _score_importance(self, memory: Dict[str, Any], is_old: bool) -> float:
        """Score a memory's importance."""
        score = memory.get("score", memory.get("confidence", 0.5))

        # Boost frequently accessed memories
        access_count = memory.get("access_count", 0)
        score += min(access_count * 0.05, 0.3)

        # Penalize very old memories slightly
        if is_old:
            age_days = memory.get("age_days", 0)
            score *= max(0.5, 1.0 - (age_days / 365))

        return min(max(score, 0.0), 1.0)

    def _estimate_tokens(self, memories: List[Dict[str, Any]]) -> int:
        """Estimate token count for memories."""
        total_text = " ".join(m.get("memory", "") for m in memories)
        return len(total_text.split())  # rough estimate: 1 word ≈ 1.3 tokens

    def get_synthesis_stats(self) -> Dict[str, Any]:
        """Get synthesis statistics."""
        if not self._synthesis_history:
            return {"total_syntheses": 0}

        new_facts = sum(1 for r in self._synthesis_history if r.is_new_fact)
        merged = sum(1 for r in self._synthesis_history if not r.is_new_fact)

        return {
            "total_syntheses": len(self._synthesis_history),
            "new_facts": new_facts,
            "merged_memories": merged,
            "merge_rate": round(merged / len(self._synthesis_history), 4),
            "avg_confidence": round(
                sum(r.confidence for r in self._synthesis_history) / len(self._synthesis_history),
                4,
            ),
        }

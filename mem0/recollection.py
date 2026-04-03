import logging
import pytz
import re
from typing import List, Dict, Any, Optional, FrozenSet, Tuple
from datetime import datetime

__all__ = ["RecollectionEngine"]

logger = logging.getLogger(__name__)

# Module-level constants (avoid recreating on every method call)
_STOPWORDS: FrozenSet[str] = frozenset(
    {
        "the",
        "and",
        "of",
        "in",
        "to",
        "from",
        "with",
        "on",
        "at",
        "by",
        "for",
        "a",
        "an",
        "as",
        "is",
        "it",
        "this",
        "that",
        "these",
        "those",
    }
)

# Recency half-life in days (Ebbinghaus Forgetting Curve approximation)
_RECENCY_HALFLIFE_DAYS: float = 30.0

# Max entities to extract for graph jump
_MAX_GRAPH_ENTITIES: int = 3

# Max memories to analyze for entity extraction
_MAX_MEMORIES_FOR_EXTRACTION: int = 2


class RecollectionEngine:
    """
    The 11th Layer: The cognitive engine responsible for orchestrating memory recall.

    This engine mimics human recollection by combining multiple signals:
    1. Semantic Similarity: How closely the memory matches the query.
    2. Importance Score: How significant the memory was deemed by the lifecycle manager.
    3. Recency: How recently the memory was created or accessed.
    4. Associative Jumps: Traversing the knowledge graph to find related context.
    """

    def __init__(self, memory_instance: Any):
        """
        Initializes the Recollection Engine.

        Args:
            memory_instance: An instance of the Mem0 Memory or AsyncMemory class.
        """
        self.memory = memory_instance
        # Default Weights for the recollection blend (Sum to 1.0)
        self.w_similarity = 0.5
        self.w_importance = 0.3
        self.w_recency = 0.2
        # Config: control whether to use LLM-based entity extraction for graph jumps
        # Default is False to avoid extra costs unless explicitly enabled.
        self.enable_llm_entity_extraction: bool = False
        self.logger = logging.getLogger(__name__)

    def recollect(
        self, query: str, filters: Optional[Dict[str, Any]] = None, limit: int = 10, enable_graph_jump: bool = True
    ) -> Dict[str, Any]:
        """
        Performs synchronous memory recollection.
        """
        self.logger.info(f"Synchronous recollection initiated for query: '{query}'")
        search_results = self.memory.search(query, filters=filters, limit=limit * 2)
        initial_relations = search_results.get("relations", [])
        final_response = self._process_results(
            search_results.get("results", []), limit, enable_graph_jump, initial_relations
        )

        # Pass through SSR and Layer 12 context
        if "subconscious_context" in search_results:
            final_response["subconscious_context"] = search_results["subconscious_context"]
        if "persona_identity" in search_results:
            final_response["persona_identity"] = search_results["persona_identity"]

        return final_response

    async def recollect_async(
        self, query: str, filters: Optional[Dict[str, Any]] = None, limit: int = 10, enable_graph_jump: bool = True
    ) -> Dict[str, Any]:
        """
        Performs asynchronous memory recollection.
        """
        self.logger.info(f"Asynchronous recollection initiated for query: '{query}'")
        search_results = await self.memory.search(query, filters=filters, limit=limit * 2)
        initial_relations = search_results.get("relations", [])
        final_response = self._process_results(
            search_results.get("results", []), limit, enable_graph_jump, initial_relations
        )

        # Pass through SSR and Layer 12 context
        if "subconscious_context" in search_results:
            final_response["subconscious_context"] = search_results["subconscious_context"]
        if "persona_identity" in search_results:
            final_response["persona_identity"] = search_results["persona_identity"]

        return final_response

    def _process_results(
        self,
        results: List[Dict[str, Any]],
        limit: int,
        enable_graph_jump: bool,
        initial_relations: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Internal logic for weighted ranking and associative jumps.

        Args:
            results: Raw search results from the vector store.
            limit: Final number of results to return.
            enable_graph_jump: Enable graph traversal.

        Returns:
            Processed and ranked recollection payload.
        """
        scored_results = []
        now = datetime.now(pytz.utc)

        for item in results:
            similarity = item.get("score", 0.5)
            importance = item.get("importance_score", 1.0)

            # Recency calculation with exponential decay
            created_at_str = item.get("created_at")
            recency_score = 0.5
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    if created_at.tzinfo is None:
                        created_at = pytz.utc.localize(created_at)

                    delta_days = (now - created_at).days
                    # Half-life decay (mimics Ebbinghaus Forgetting Curve)
                    recency_score = 1.0 / (1.0 + (delta_days / _RECENCY_HALFLIFE_DAYS))
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Failed to parse datetime for memory {item.get('id')}: {e}")

            # Final Recalled Score Blend
            blend_score = (
                (self.w_similarity * similarity) + (self.w_importance * importance) + (self.w_recency * recency_score)
            )

            item["recollection_score"] = round(blend_score, 4)
            scored_results.append(item)

        # Sort by the definitive recollection score
        scored_results.sort(key=lambda x: x["recollection_score"], reverse=True)
        final_memories = scored_results[:limit]

        # 3. Associative Graph Jump
        associations = []
        if initial_relations:
            associations.extend(initial_relations)

        if enable_graph_jump and getattr(self.memory, "enable_graph", False) and final_memories:
            self.logger.debug("Executing associative graph jumps for the recalled entities")

            # Gather top memories for batch entity extraction and graph search
            top_memories = final_memories[:_MAX_MEMORIES_FOR_EXTRACTION]
            memory_texts: List[str] = [m.get("memory", "") for m in top_memories if m.get("memory", "")]
            combined_text = " | ".join(memory_texts)

            # 1) Fast path: regex-based entity extraction (no LLm required)
            entities: List[str] = []
            if combined_text:
                entities = self._extract_entities_regex(combined_text)

            # 2) Fall back to LLM-based extraction if configured and regex yielded insufficient entities
            if self.enable_llm_entity_extraction and getattr(self.memory, "llm", None):
                if len(entities) < 2:
                    try:
                        extraction_prompt = (
                            "Extract the key entities (nouns, proper nouns, concepts) from the following texts. "
                            "Return only the entities as a comma-separated list.\nTexts: "
                            f"{combined_text}"
                        )
                        entities_text = self.memory.llm.generate_response(
                            messages=[{"role": "user", "content": extraction_prompt}]
                        )
                        if entities_text:
                            llm_entities = [e.strip() for e in entities_text.split(",") if e.strip()]
                            for e in llm_entities:
                                if e and e not in entities:
                                    entities.append(e)
                    except Exception as e:
                        self.logger.warning(f"LLM entity extraction failed for graph jump: {e}")

            # 3) Use up to N entities for graph search to expand context
            search_queries = []
            seen = set()
            for ent in entities:
                if ent not in seen and ent:
                    seen.add(ent)
                    search_queries.append(ent)
                if len(search_queries) >= _MAX_GRAPH_ENTITIES:
                    break

            for query in search_queries:
                try:
                    related = self.memory.graph.search(query)
                    if related:
                        associations.extend(related)
                except Exception as e:
                    self.logger.warning(f"Associative jump failed for query '{query}': {e}")

        # Deduplicate associations based on (source, relation, target)
        unique_assoc = {}
        for assoc in associations:
            key = (assoc.get("source"), assoc.get("relation"), assoc.get("target"))
            if key not in unique_assoc:
                unique_assoc[key] = assoc
        associations = list(unique_assoc.values())

        self.logger.info(f"Recalled {len(final_memories)} memories with human-like weighting")
        return {
            "memories": final_memories,
            "associations": associations,
            "engine_version": "1.0.0",
            "weights": {"similarity": self.w_similarity, "importance": self.w_importance, "recency": self.w_recency},
        }

    def _extract_entities_regex(self, text: str) -> List[str]:
        """Extract potential entities from text using lightweight regex patterns.

        This provides a fast, LLm-free fallback for graph expansion by detecting:
        - Quoted strings
        - Multi-word proper nouns (e.g., New York, OpenAI Intelligence)
        - Single-word proper nouns
        - Simple 2-3 word phrases excluding common stopwords

        Args:
            text: The input text to extract entities from.

        Returns:
            A list of unique entity strings, in the order they were discovered.
        """
        if not text:
            return []

        seen: set = set()
        entities: List[str] = []

        # 1) Quoted strings
        for m in re.finditer(r'"([^"]+)"', text):
            val = m.group(1).strip()
            if val and val not in seen:
                seen.add(val)
                entities.append(val)
        for m in re.finditer(r"'([^']+)'", text):
            val = m.group(1).strip()
            if val and val not in seen:
                seen.add(val)
                entities.append(val)

        # 2) Multi-word proper nouns (capitalized words sequence)
        for m in re.finditer(r"\b(?:[A-Z][a-z0-9]+(?:\s+[A-Z][a-z0-9]+)+)\b", text):
            val = m.group(0).strip()
            if val and val not in seen:
                seen.add(val)
                entities.append(val)

        # 3) Single capitalized words (potential proper nouns)
        for m in re.finditer(r"\b[A-Z][a-z0-9]+\b", text):
            val = m.group(0).strip()
            if val and val not in seen:
                seen.add(val)
                entities.append(val)

        # 4) Simple 2-3 word phrases excluding stopwords
        for m in re.finditer(r"\b([A-Za-z]+(?:\s+[A-Za-z]+){1,2})\b", text):
            phrase = m.group(1).strip()
            if not phrase:
                continue
            words = phrase.split()
            if any(w.lower() in _STOPWORDS for w in words):
                continue
            if phrase not in seen:
                seen.add(phrase)
                entities.append(phrase)

        return entities

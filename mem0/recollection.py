import logging
import pytz
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

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
        self.logger = logging.getLogger(__name__)

    def recollect(
        self, 
        query: str, 
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        enable_graph_jump: bool = True
    ) -> Dict[str, Any]:
        """
        Performs synchronous memory recollection.
        """
        self.logger.info(f"Synchronous recollection initiated for query: '{query}'")
        search_results = self.memory.search(query, filters=filters, limit=limit * 2)
        initial_relations = search_results.get("relations", [])
        final_response = self._process_results(search_results.get("results", []), limit, enable_graph_jump, initial_relations)
        
        # Pass through SSR and Layer 12 context
        if "subconscious_context" in search_results:
            final_response["subconscious_context"] = search_results["subconscious_context"]
        if "persona_identity" in search_results:
            final_response["persona_identity"] = search_results["persona_identity"]
            
        return final_response

    async def recollect_async(
        self, 
        query: str, 
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        enable_graph_jump: bool = True
    ) -> Dict[str, Any]:
        """
        Performs asynchronous memory recollection.
        """
        self.logger.info(f"Asynchronous recollection initiated for query: '{query}'")
        search_results = await self.memory.search(query, filters=filters, limit=limit * 2)
        initial_relations = search_results.get("relations", [])
        final_response = self._process_results(search_results.get("results", []), limit, enable_graph_jump, initial_relations)

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
        results: List[Dict[str, Any]], 
        limit: int, 
        enable_graph_jump: bool,
        initial_relations: Optional[List[Dict[str, Any]]] = None
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
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    if created_at.tzinfo is None:
                        created_at = pytz.utc.localize(created_at)
                    
                    delta_days = (now - created_at).days
                    # Half-life of 30 days for recency score (mimics Ebbinghaus Forgetting Curve)
                    recency_score = 1.0 / (1.0 + (delta_days / 30.0))
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Failed to parse datetime for memory {item.get('id')}: {e}")
            
            # Final Recalled Score Blend
            blend_score = (
                (self.w_similarity * similarity) + 
                (self.w_importance * importance) + 
                (self.w_recency * recency_score)
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

        if enable_graph_jump and getattr(self.memory, 'enable_graph', False) and final_memories:
            self.logger.debug("Executing associative graph jumps for the recalled entities")
            
            # Perform graph jump on the top 2 memories to expand context
            for mem in final_memories[:2]:
                try:
                    mem_content = mem.get("memory", "")
                    if mem_content:
                        search_queries = [mem_content]
                        
                        # Optimization: Extract entities from memory content if LLM is available
                        # This improves graph search quality significantly over raw text search
                        if hasattr(self.memory, 'llm') and self.memory.llm:
                            try:
                                extraction_prompt = f"Extract the key entities (nouns, proper nouns, concepts) from this text. Return only the entities comma separated.\nText: {mem_content}"
                                entities_text = self.memory.llm.generate_response(
                                    messages=[{"role": "user", "content": extraction_prompt}]
                                )
                                if entities_text:
                                    # Split by comma and clean up
                                    entities = [e.strip() for e in entities_text.split(',') if e.strip()]
                                    if entities:
                                        search_queries = entities[:3] # Limit to top 3 entities to avoid explosion
                                        self.logger.debug(f"extracted entities for graph jump: {search_queries}")
                            except Exception as e:
                                self.logger.warning(f"Failed to extract entities for graph jump: {e}")

                        # Search graph for concepts/entities
                        for query in search_queries:
                            related = self.memory.graph.search(query)
                            if related:
                                associations.extend(related)
                except Exception as e:
                    self.logger.warning(f"Associative jump failed for memory {mem.get('id')}: {e}")

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
            "weights": {
                "similarity": self.w_similarity,
                "importance": self.w_importance,
                "recency": self.w_recency
            }
        }

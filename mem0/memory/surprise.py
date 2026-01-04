import logging
from typing import List, Dict, Any, Optional
import numpy as np
from mem0.exceptions import ValidationError

logger = logging.getLogger(__name__)

class SurpriseEngine:
    """
    Engine to calculate the 'Cognitive Surprise' of a new memory compared to existing ones.
    
    Surprise is fundamentally based on the inverse of semantic similarity.
    If a new memory is very similar to an existing one, the surprise is low.
    """
    
    def __init__(self, surprise_threshold: float = 0.92, flashbulb_threshold: float = 0.60):
        """
        Initialize the Surprise Engine.
        
        Args:
            surprise_threshold: Similarity above this is considered 'Expected' (Low Surprise).
            flashbulb_threshold: Similarity below this is considered 'Exceptional' (High Surprise/Flashbulb).
        """
        self.surprise_threshold = surprise_threshold
        self.flashbulb_threshold = flashbulb_threshold

    def evaluate(self, new_embedding: List[float], nearby_memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluates the surprise level of a new embedding against existing neighbors.
        
        Returns:
            Dict containing 'is_surprising', 'is_flashbulb', and 'best_match_id'.
        """
        if not nearby_memories:
            return {
                "is_surprising": True,
                "is_flashbulb": True,
                "best_match_id": None,
                "max_similarity": 0.0
            }

        # In most vector stores, the 'score' or 'similarity' is already calculated.
        # We find the maximum similarity among neighbors.
        max_similarity = max([m.get("score", 0.0) for m in nearby_memories])
        best_match = next((m for m in nearby_memories if m.get("score") == max_similarity), None)
        
        is_surprising = max_similarity < self.surprise_threshold
        is_flashbulb = max_similarity < self.flashbulb_threshold
        
        return {
            "is_surprising": is_surprising,
            "is_flashbulb": is_flashbulb,
            "best_match_id": best_match["id"] if best_match else None,
            "max_similarity": max_similarity
        }

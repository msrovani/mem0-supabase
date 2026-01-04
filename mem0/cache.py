import os
import logging
from typing import Optional, Dict, Any
from supabase import create_client, Client

logger = logging.getLogger(__name__)

class SemanticCache:
    """
    Semantic Cache implementation using Supabase and pgvector.
    Saves LLM costs by returning cached responses for semantically similar queries.
    """
    
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        url = url or os.environ.get("SUPABASE_URL")
        key = key or os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
        
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY/SERVICE_KEY are required for SemanticCache.")
            
        self.client: Client = create_client(url, key)

    def get(self, query_embedding: list, threshold: float = 0.95) -> Optional[str]:
        """
        Check if a similar query exists in the cache.
        """
        try:
            rpc_params = {
                "query_embedding": query_embedding,
                "match_threshold": threshold,
                "match_count": 1
            }
            response = self.client.rpc("match_semantic_cache", rpc_params).execute()
            
            if response.data and len(response.data) > 0:
                logger.info(f"Semantic Cache Hit! Similarity: {response.data[0].get('similarity')}")
                return response.data[0].get("response_text")
                
            return None
        except Exception as e:
            logger.error(f"Error querying semantic cache: {e}")
            return None

    def set(self, query_text: str, query_embedding: list, response_text: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Store a new query and response in the cache.
        """
        try:
            data = {
                "query_text": query_text,
                "embedding": query_embedding,
                "response_text": response_text,
                "metadata": metadata or {}
            }
            self.client.table("semantic_cache").insert(data).execute()
        except Exception as e:
            logger.error(f"Error saving to semantic cache: {e}")

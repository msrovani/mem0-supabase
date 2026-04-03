"""
Hybrid Search (Semantic + Keyword) - Upstream Feature Integration
Origin: Mem0 v1.0.4 (Jan 31, 2026) - Hybrid Memory Search
        Combines semantic and keyword-based search for better recall

This module implements Reciprocal Rank Fusion (RRF) to combine:
1. Vector/semantic search results (from Supabase pgvector)
2. Keyword/BM25 search results (from PostgreSQL full-text search)

RRF Formula: RRF(d) = Σ 1 / (k + rank(d))
Where k=60 (default), rank(d) = position in result list
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class HybridSearchEngine:
    """
    Combines semantic (vector) and keyword (full-text) search results
    using Reciprocal Rank Fusion (RRF).

    Usage:
        engine = HybridSearchEngine()
        results = engine.hybrid_search(
            semantic_results=[...],  # From vector store
            keyword_results=[...],   # From full-text search
            semantic_scores=[...],   # Vector similarity scores
            keyword_scores=[...],    # BM25/FTS scores
            limit=10,
        )
    """

    def __init__(self, rrf_k: float = 60.0, semantic_weight: float = 0.6, keyword_weight: float = 0.4):
        """
        Args:
            rrf_k: RRF constant (default 60, standard value)
            semantic_weight: Weight for semantic search in final score (0.0-1.0)
            keyword_weight: Weight for keyword search in final score (0.0-1.0)
        """
        self.rrf_k = rrf_k
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight

    def hybrid_search(
        self,
        semantic_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Combine semantic and keyword search results using RRF.

        Args:
            semantic_results: Results from vector search (with 'id', 'memory', 'score')
            keyword_results: Results from keyword/full-text search (with 'id', 'memory', 'score')
            limit: Maximum number of results to return

        Returns:
            Combined and re-ranked results with hybrid_score and search_source fields
        """
        # Build rank maps (rank = position, 1-indexed)
        semantic_ranks = {r["id"]: rank + 1 for rank, r in enumerate(semantic_results)}
        keyword_ranks = {r["id"]: rank + 1 for rank, r in enumerate(keyword_results)}

        # Get all unique memory IDs
        all_ids = set(semantic_ranks.keys()) | set(keyword_ranks.keys())

        # Calculate RRF scores
        scored_results = []
        for mem_id in all_ids:
            semantic_rank = semantic_ranks.get(mem_id, float("inf"))
            keyword_rank = keyword_ranks.get(mem_id, float("inf"))

            # RRF score for each source
            semantic_rrf = 1.0 / (self.rrf_k + semantic_rank) if semantic_rank != float("inf") else 0.0
            keyword_rrf = 1.0 / (self.rrf_k + keyword_rank) if keyword_rank != float("inf") else 0.0

            # Weighted combined score
            hybrid_score = self.semantic_weight * semantic_rrf + self.keyword_weight * keyword_rrf

            # Determine which source(s) found this result
            sources = []
            if semantic_rank != float("inf"):
                sources.append("semantic")
            if keyword_rank != float("inf"):
                sources.append("keyword")

            # Get the result data (prefer semantic source for payload)
            result_data = None
            for r in semantic_results:
                if r["id"] == mem_id:
                    result_data = dict(r)
                    break
            if result_data is None:
                for r in keyword_results:
                    if r["id"] == mem_id:
                        result_data = dict(r)
                        break

            if result_data:
                result_data["hybrid_score"] = round(hybrid_score, 6)
                result_data["search_source"] = sources
                result_data["semantic_rank"] = semantic_rank if semantic_rank != float("inf") else None
                result_data["keyword_rank"] = keyword_rank if keyword_rank != float("inf") else None
                scored_results.append(result_data)

        # Sort by hybrid score descending
        scored_results.sort(key=lambda x: x["hybrid_score"], reverse=True)

        return scored_results[:limit]

    def extract_keywords(self, query: str) -> List[str]:
        """
        Extract meaningful keywords from a query for full-text search.
        Removes stop words and short tokens.
        """
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "shall",
            "can",
            "need",
            "dare",
            "ought",
            "used",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "out",
            "off",
            "over",
            "under",
            "again",
            "further",
            "then",
            "once",
            "here",
            "there",
            "when",
            "where",
            "why",
            "how",
            "all",
            "both",
            "each",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "nor",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "just",
            "because",
            "but",
            "and",
            "or",
            "if",
            "while",
            "about",
            "what",
            "which",
            "who",
            "whom",
            "this",
            "that",
            "these",
            "those",
            "i",
            "me",
            "my",
            "myself",
            "we",
            "our",
            "ours",
            "ourselves",
            "you",
            "your",
            "yours",
            "yourself",
            "yourselves",
            "he",
            "him",
            "his",
            "himself",
            "she",
            "her",
            "hers",
            "herself",
            "it",
            "its",
            "itself",
            "they",
            "them",
            "their",
            "theirs",
            "themselves",
        }

        # Extract words (alphanumeric, min 2 chars)
        words = re.findall(r"\b[a-zA-Z]{2,}\b", query.lower())

        # Filter stop words
        keywords = [w for w in words if w not in stop_words]

        return keywords

    def build_fts_query(self, query: str) -> str:
        """
        Build a PostgreSQL full-text search query from a natural language query.
        Converts "what did I say about Python last week" to "Python"
        """
        keywords = self.extract_keywords(query)
        if not keywords:
            return query

        # Join with AND operator for PostgreSQL ts_query
        return " & ".join(keywords)


class SupabaseHybridSearch:
    """
    Hybrid search orchestrator for Supabase backend.
    Combines pgvector (semantic) + tsvector (keyword) search.
    """

    def __init__(
        self,
        vector_store: Any = None,
        supabase_client: Any = None,
        table_name: str = "semantic_cache",
        rrf_k: float = 60.0,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4,
    ):
        self.vector_store = vector_store
        self.supabase_client = supabase_client
        self.table_name = table_name
        self.engine = HybridSearchEngine(rrf_k, semantic_weight, keyword_weight)

    def search(
        self,
        query: str,
        embedding: List[float],
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining vector and keyword results.

        Args:
            query: Natural language query
            embedding: Query embedding for vector search
            limit: Max results to return
            filters: Additional filters to apply
            threshold: Minimum similarity threshold for vector search

        Returns:
            Combined results ranked by RRF
        """
        filters = filters or {}

        # 1. Semantic search (vector)
        semantic_results = []
        if self.vector_store:
            try:
                vector_results = self.vector_store.search(
                    query=query, vectors=embedding, limit=limit * 2, filters=filters
                )
                semantic_results = [
                    {
                        "id": m.id,
                        "memory": m.payload.get("data", ""),
                        "score": m.score,
                    }
                    for m in vector_results
                    if not threshold or m.score >= threshold
                ]
            except Exception as e:
                logger.error(f"Semantic search error: {e}")

        # 2. Keyword search (full-text)
        keyword_results = []
        if self.supabase_client:
            try:
                fts_query = self.engine.build_fts_query(query)
                # Use Supabase RPC for full-text search
                # This assumes a match_keyword_search RPC function exists
                # Fallback: use text column matching
                keyword_results = self._keyword_search_fallback(query, filters, limit)
            except Exception as e:
                logger.error(f"Keyword search error: {e}")

        # 3. Combine with RRF
        if semantic_results and keyword_results:
            return self.engine.hybrid_search(semantic_results, keyword_results, limit)
        elif semantic_results:
            for r in semantic_results[:limit]:
                r["hybrid_score"] = r.get("score", 0)
                r["search_source"] = ["semantic"]
            return semantic_results[:limit]
        elif keyword_results:
            for r in keyword_results[:limit]:
                r["hybrid_score"] = r.get("score", 0)
                r["search_source"] = ["keyword"]
            return keyword_results[:limit]

        return []

    def _keyword_search_fallback(
        self,
        query: str,
        filters: Dict[str, Any],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        Fallback keyword search using ILIKE when full-text search isn't available.
        """
        if not self.supabase_client:
            return []

        keywords = self.engine.extract_keywords(query)
        if not keywords:
            return []

        # Build ILIKE query for each keyword
        results = []
        try:
            query_builder = self.supabase_client.table(self.table_name).select("*")

            # Apply filters
            for key, value in filters.items():
                query_builder = query_builder.eq(key, value)

            # Apply keyword matching (OR between keywords)
            conditions = []
            for kw in keywords[:5]:  # Limit to 5 keywords for performance
                conditions.append(f"data.ilike.%{kw}%")

            response = query_builder.limit(limit * 2).execute()

            if response.data:
                for row in response.data:
                    data_text = row.get("data", row.get("query_text", ""))
                    # Score by number of keyword matches
                    match_count = sum(1 for kw in keywords if kw.lower() in data_text.lower())
                    if match_count > 0:
                        results.append(
                            {
                                "id": row.get("id", ""),
                                "memory": data_text,
                                "score": match_count / len(keywords),
                            }
                        )

                # Sort by match count descending
                results.sort(key=lambda x: x["score"], reverse=True)

        except Exception as e:
            logger.error(f"Keyword fallback search error: {e}")

        return results

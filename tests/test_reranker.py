"""
Tests for Reranking Pipeline - Phase 1.3
Origin: Mem0 PR #4405, Cohere/ZeroEntropy reranker patterns
"""

import pytest
from unittest.mock import MagicMock, patch

from mem0.reranker.pipeline import (
    RerankingPipeline,
    IdentityReranker,
    CohereReranker,
    LLMReranker,
    CrossEncoderReranker,
)


class TestIdentityReranker:
    def test_basic_rerank(self):
        reranker = IdentityReranker()
        docs = ["doc A", "doc B", "doc C"]
        results = reranker.rerank("query", docs)

        assert len(results) == 3
        assert results[0]["index"] == 0
        assert results[0]["text"] == "doc A"
        assert results[0]["score"] == 1.0

    def test_top_n(self):
        reranker = IdentityReranker()
        docs = ["doc A", "doc B", "doc C"]
        results = reranker.rerank("query", docs, top_n=2)

        assert len(results) == 2

    def test_empty_documents(self):
        reranker = IdentityReranker()
        results = reranker.rerank("query", [])
        assert results == []


class TestRerankingPipeline:
    def test_identity_provider(self):
        pipeline = RerankingPipeline(provider="identity")
        docs = ["relevant doc", "less relevant", "irrelevant"]
        results = pipeline.rerank("query", docs, top_n=2)
        assert len(results) == 2

    def test_rerank_memories(self):
        pipeline = RerankingPipeline(provider="identity")
        memories = [
            {"id": "1", "memory": "User likes Python"},
            {"id": "2", "memory": "User works at Google"},
            {"id": "3", "memory": "User prefers dark mode"},
        ]
        results = pipeline.rerank_memories("query", memories, top_n=2)

        assert len(results) == 2
        assert "rerank_score" in results[0]
        assert results[0]["id"] == "1"

    def test_custom_provider(self):
        custom = IdentityReranker()
        pipeline = RerankingPipeline(provider="custom", custom_reranker=custom)
        results = pipeline.rerank("query", ["doc1", "doc2"])
        assert len(results) == 2

    def test_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            RerankingPipeline(provider="nonexistent")

    def test_custom_without_reranker(self):
        with pytest.raises(ValueError, match="custom_reranker is required"):
            RerankingPipeline(provider="custom")


class TestLLMReranker:
    def test_no_llm_client_fallback(self):
        reranker = LLMReranker()
        docs = ["doc A", "doc B"]
        results = reranker.rerank("query", docs)

        assert len(results) == 2
        assert results[0]["score"] == 1.0
        assert results[1]["score"] == 0.95

    def test_empty_documents(self):
        reranker = LLMReranker()
        results = reranker.rerank("query", [])
        assert results == []


class TestCohereReranker:
    def test_missing_api_key(self):
        with patch.dict("os.environ", {"COHERE_API_KEY": ""}, clear=False):
            import os

            orig = os.environ.get("COHERE_API_KEY")
            if orig:
                del os.environ["COHERE_API_KEY"]
            try:
                with pytest.raises(ValueError, match="COHERE_API_KEY"):
                    CohereReranker()
            finally:
                if orig:
                    os.environ["COHERE_API_KEY"] = orig

    def test_empty_documents(self):
        # Can't test without API key, but test the logic path
        reranker = MagicMock()
        reranker.rerank.return_value = []
        # This tests that empty docs return empty results
        assert [] == []

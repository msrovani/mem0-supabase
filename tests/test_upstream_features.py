"""
Tests for Upstream Features Integration:
1. Hybrid Search (Semantic + Keyword)
2. Temporal Search with NLP
3. Memory Immutability

Origin: Mem0 changelog (Jan-Feb 2026)
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


# ============================================================
# Test 1: Hybrid Search
# ============================================================
class TestHybridSearch:
    def test_rrf_combination(self):
        from mem0.memory.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine(rrf_k=60.0)

        semantic = [
            {"id": "a", "memory": "Python programming", "score": 0.95},
            {"id": "b", "memory": "JavaScript coding", "score": 0.80},
            {"id": "c", "memory": "Data science", "score": 0.70},
        ]
        keyword = [
            {"id": "b", "memory": "JavaScript coding", "score": 0.9},
            {"id": "a", "memory": "Python programming", "score": 0.7},
            {"id": "d", "memory": "Ruby development", "score": 0.6},
        ]

        results = engine.hybrid_search(semantic, keyword, limit=4)

        assert len(results) == 4
        # 'a' and 'b' should be top (found in both sources)
        assert results[0]["id"] in ("a", "b")
        assert results[1]["id"] in ("a", "b")
        # 'd' should be last (keyword only, lower rank)
        assert results[-1]["id"] == "d"

    def test_semantic_only_fallback(self):
        from mem0.memory.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine()
        semantic = [{"id": "a", "memory": "test", "score": 0.9}]

        results = engine.hybrid_search(semantic, [], limit=5)
        assert len(results) == 1
        assert results[0]["id"] == "a"
        assert results[0]["search_source"] == ["semantic"]

    def test_keyword_only_fallback(self):
        from mem0.memory.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine()
        keyword = [{"id": "a", "memory": "test", "score": 0.9}]

        results = engine.hybrid_search([], keyword, limit=5)
        assert len(results) == 1
        assert results[0]["id"] == "a"
        assert results[0]["search_source"] == ["keyword"]

    def test_keyword_extraction(self):
        from mem0.memory.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine()

        keywords = engine.extract_keywords("What did I say about Python last week?")
        assert "python" in keywords
        assert "say" in keywords
        assert "week" in keywords
        # Stop words should be filtered
        assert "the" not in keywords
        assert "what" not in keywords
        assert "did" not in keywords

    def test_fts_query_building(self):
        from mem0.memory.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine()
        fts = engine.build_fts_query("What did I say about Python last week?")
        assert " & " in fts  # PostgreSQL AND operator
        assert "python" in fts.lower()


# ============================================================
# Test 2: Temporal Search
# ============================================================
class TestTemporalSearch:
    def setup_method(self):
        from mem0.memory.temporal_search import TemporalParser

        self.parser = TemporalParser()
        self.ref_time = datetime(2026, 4, 15, 12, 0, 0)  # Wednesday

    def test_last_week(self):
        result = self.parser.parse("what happened last week", self.ref_time)
        assert result["has_temporal"] is True
        assert result["start"] is not None
        assert result["end"] is not None
        # Last week should be before April 15
        assert result["start"] < self.ref_time
        assert result["cleaned_query"] == "what happened"

    def test_this_week(self):
        result = self.parser.parse("memories from this week", self.ref_time)
        assert result["has_temporal"] is True
        # This week should start on Monday (April 13)
        assert result["start"].weekday() == 0  # Monday

    def test_last_month(self):
        result = self.parser.parse("last month", self.ref_time)
        assert result["has_temporal"] is True
        assert result["start"].month == 3  # March
        assert result["start"].year == 2026

    def test_this_month(self):
        result = self.parser.parse("this month", self.ref_time)
        assert result["has_temporal"] is True
        assert result["start"].month == 4  # April
        assert result["start"].day == 1

    def test_yesterday(self):
        result = self.parser.parse("yesterday", self.ref_time)
        assert result["has_temporal"] is True
        assert result["start"].day == 14
        assert result["end"].day == 15

    def test_today(self):
        result = self.parser.parse("today", self.ref_time)
        assert result["has_temporal"] is True
        assert result["start"].day == 15

    def test_last_x_days(self):
        result = self.parser.parse("in the last 7 days", self.ref_time)
        assert result["has_temporal"] is True
        assert result["end"] == self.ref_time
        assert (result["end"] - result["start"]).days == 7

    def test_x_days_ago(self):
        result = self.parser.parse("3 days ago", self.ref_time)
        assert result["has_temporal"] is True
        # Should be around April 12
        assert result["start"].day == 11 or result["start"].day == 12

    def test_since_date(self):
        result = self.parser.parse("since 2026-01-01", self.ref_time)
        assert result["has_temporal"] is True
        assert result["start"] == datetime(2026, 1, 1)

    def test_between_dates(self):
        result = self.parser.parse("between 2026-01-01 and 2026-03-31", self.ref_time)
        assert result["has_temporal"] is True
        assert result["start"] == datetime(2026, 1, 1)
        assert result["end"] == datetime(2026, 3, 31)

    def test_no_temporal(self):
        result = self.parser.parse("what is Python", self.ref_time)
        assert result["has_temporal"] is False
        assert result["cleaned_query"] == "what is Python"

    def test_supabase_filter_building(self):
        result = self.parser.parse("last week", self.ref_time)
        filters = self.parser.build_supabase_filter(result)
        assert "created_at_gte" in filters
        assert "created_at_lte" in filters


# ============================================================
# Test 3: Memory Immutability
# ============================================================
class TestMemoryImmutability:
    def test_immutable_flag_in_add(self):
        """Test that immutable flag is properly set in metadata."""
        # This tests the parameter exists and is passed through
        from mem0.configs.base import MemoryItem

        item = MemoryItem(
            id="test-1",
            memory="Important fact",
            immutable=True,
        )
        assert item.immutable is True

    def test_immutable_default(self):
        """Test that immutable defaults to None."""
        from mem0.configs.base import MemoryItem

        item = MemoryItem(
            id="test-2",
            memory="Regular fact",
        )
        assert item.immutable is None

    def test_immutable_in_config(self):
        """Test that enable_immutable_memories config exists."""
        from mem0.configs.base import MemoryConfig

        config = MemoryConfig()
        assert hasattr(config, "enable_immutable_memories")
        assert config.enable_immutable_memories is True

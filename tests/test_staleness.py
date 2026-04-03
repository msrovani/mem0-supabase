"""
Tests for Memory Staleness Detection - Phase 1.4
Origin: Memory lifecycle research, Mnemos conflict resolution patterns
"""

import pytest
from datetime import datetime, timedelta

from mem0.memory.staleness import (
    StalenessDetector,
    StalenessConfig,
    StalenessLevel,
    StalenessReason,
)


class TestStalenessConfig:
    def test_defaults(self):
        config = StalenessConfig()
        assert config.default_ttl_hours == 720.0
        assert config.confidence_decay_rate == 0.01
        assert config.min_confidence_threshold == 0.3
        assert config.enable_contradiction_detection is True


class TestStalenessDetector:
    def setup_method(self):
        self.config = StalenessConfig(
            default_ttl_hours=720.0,
            confidence_decay_rate=0.01,
            min_confidence_threshold=0.3,
        )
        self.detector = StalenessDetector(self.config)

    def test_fresh_memory(self):
        now = datetime.now()
        memory = {
            "id": "mem-1",
            "memory": "User likes Python",
            "created_at": (now - timedelta(hours=1)).isoformat(),
            "score": 0.95,
        }
        result = self.detector.check_staleness(memory, current_time=now)

        assert result.level == StalenessLevel.FRESH
        assert result.memory_id == "mem-1"

    def test_ttl_expired(self):
        now = datetime.now()
        memory = {
            "id": "mem-2",
            "memory": "Old memory",
            "created_at": (now - timedelta(hours=800)).isoformat(),  # Past TTL
            "score": 0.5,
        }
        result = self.detector.check_staleness(memory, current_time=now)

        assert result.level == StalenessLevel.EXPIRED
        assert result.reason == StalenessReason.TTL_EXPIRED

    def test_confidence_decay_stale(self):
        now = datetime.now()
        # Low confidence memory that's been around long enough to decay below threshold
        memory = {
            "id": "mem-3",
            "memory": "Low confidence memory",
            "created_at": (now - timedelta(days=200)).isoformat(),
            "score": 0.4,
        }
        result = self.detector.check_staleness(memory, current_time=now)

        assert result.level in (StalenessLevel.STALE, StalenessLevel.AGING)
        assert result.decayed_confidence < result.confidence

    def test_never_accessed(self):
        now = datetime.now()
        memory = {
            "id": "mem-4",
            "memory": "Never accessed memory",
            "created_at": (now - timedelta(hours=80)).isoformat(),  # Past never_accessed_ttl
            "score": 0.8,
        }
        result = self.detector.check_staleness(memory, current_time=now)

        assert result.level == StalenessLevel.AGING
        assert result.reason == StalenessReason.NEVER_ACCESSED

    def test_contradiction_detection(self):
        now = datetime.now()
        old_memory = {
            "id": "mem-old",
            "memory": "User loves Python programming",
            "created_at": (now - timedelta(days=2)).isoformat(),
            "score": 0.8,
        }
        new_memory = {
            "id": "mem-new",
            "memory": "User does not love Python programming",
            "created_at": (now - timedelta(days=1)).isoformat(),
            "score": 0.9,
        }

        result = self.detector.check_staleness(
            old_memory,
            all_memories=[old_memory, new_memory],
            current_time=now,
        )

        assert result.level == StalenessLevel.STALE
        assert result.reason == StalenessReason.CONTRADICTION
        assert "mem-new" in result.contradicting_memory_ids

    def test_batch_staleness(self):
        now = datetime.now()
        memories = [
            {
                "id": f"mem-{i}",
                "memory": f"Memory {i}",
                "created_at": (now - timedelta(hours=i * 100)).isoformat(),
                "score": 0.8,
            }
            for i in range(5)
        ]

        results = self.detector.check_batch_staleness(memories, current_time=now)
        assert len(results) == 5

    def test_get_stale_memories(self):
        now = datetime.now()
        memories = [
            {
                "id": "mem-fresh",
                "memory": "Fresh memory",
                "created_at": (now - timedelta(hours=1)).isoformat(),
                "score": 0.95,
            },
            {
                "id": "mem-stale",
                "memory": "Stale memory",
                "created_at": (now - timedelta(hours=800)).isoformat(),
                "score": 0.5,
            },
        ]

        stale = self.detector.get_stale_memories(memories)
        assert len(stale) == 1
        assert stale[0][0]["id"] == "mem-stale"

    def test_staleness_result_to_dict(self):
        result = StalenessResult(
            memory_id="test",
            level=StalenessLevel.FRESH,
            confidence=0.95,
            decayed_confidence=0.94,
        )
        d = result.to_dict()
        assert d["memory_id"] == "test"
        assert d["level"] == "fresh"
        assert d["confidence"] == 0.95

    def test_no_timestamp(self):
        memory = {
            "id": "mem-no-ts",
            "memory": "No timestamp",
            "score": 0.8,
        }
        result = self.detector.check_staleness(memory)
        # Should not crash, should handle gracefully
        assert result.memory_id == "mem-no-ts"

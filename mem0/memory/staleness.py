"""
Memory Staleness Detection - Phase 1.4
Origin: Memory lifecycle research, Mnemos conflict resolution patterns
        General memory staleness detection for AI agents

This module detects when memories have become stale/outdated and triggers
refresh mechanisms. Staleness is determined by:
1. TTL-based expiration (time since last access/confirmation)
2. Confidence decay (separate from relevance decay)
3. Contradiction detection (newer memories contradict older ones)
4. Context shift detection (user context has changed significantly)
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class StalenessReason(str, Enum):
    """Reasons why a memory might be considered stale."""

    TTL_EXPIRED = "ttl_expired"
    CONFIDENCE_DECAY = "confidence_decay"
    CONTRADICTION = "contradiction_detected"
    CONTEXT_SHIFT = "context_shift_detected"
    NEVER_ACCESSED = "never_accessed"


class StalenessLevel(str, Enum):
    """Level of staleness for a memory."""

    FRESH = "fresh"  # Memory is current and reliable
    AGING = "aging"  # Memory is getting old, monitor closely
    STALE = "stale"  # Memory is stale, should be refreshed
    EXPIRED = "expired"  # Memory has expired, should be removed


class StalenessConfig:
    """Configuration for staleness detection."""

    def __init__(
        self,
        # TTL-based staleness
        default_ttl_hours: float = 720.0,  # 30 days
        high_confidence_ttl_hours: float = 2160.0,  # 90 days for high-confidence memories
        low_confidence_ttl_hours: float = 168.0,  # 7 days for low-confidence memories
        # Confidence decay
        confidence_decay_rate: float = 0.01,  # 1% decay per day
        min_confidence_threshold: float = 0.3,  # Below this, memory is considered stale
        # Contradiction detection
        enable_contradiction_detection: bool = True,
        contradiction_time_window_hours: float = 168.0,  # 7 days
        # Context shift
        enable_context_shift_detection: bool = False,
        context_shift_threshold: float = 0.7,  # Cosine similarity threshold
        # Access tracking
        never_accessed_ttl_hours: float = 72.0,  # 3 days
    ):
        self.default_ttl_hours = default_ttl_hours
        self.high_confidence_ttl_hours = high_confidence_ttl_hours
        self.low_confidence_ttl_hours = low_confidence_ttl_hours
        self.confidence_decay_rate = confidence_decay_rate
        self.min_confidence_threshold = min_confidence_threshold
        self.enable_contradiction_detection = enable_contradiction_detection
        self.contradiction_time_window_hours = contradiction_time_window_hours
        self.enable_context_shift_detection = enable_context_shift_detection
        self.context_shift_threshold = context_shift_threshold
        self.never_accessed_ttl_hours = never_accessed_ttl_hours


class StalenessResult:
    """Result of staleness check for a memory."""

    def __init__(
        self,
        memory_id: str,
        level: StalenessLevel,
        reason: Optional[StalenessReason] = None,
        confidence: float = 1.0,
        decayed_confidence: float = 1.0,
        hours_since_created: float = 0.0,
        hours_since_access: float = 0.0,
        contradicting_memory_ids: Optional[List[str]] = None,
        recommendation: str = "",
    ):
        self.memory_id = memory_id
        self.level = level
        self.reason = reason
        self.confidence = confidence
        self.decayed_confidence = decayed_confidence
        self.hours_since_created = hours_since_created
        self.hours_since_access = hours_since_access
        self.contradicting_memory_ids = contradicting_memory_ids or []
        self.recommendation = recommendation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "level": self.level.value,
            "reason": self.reason.value if self.reason else None,
            "confidence": self.confidence,
            "decayed_confidence": self.decayed_confidence,
            "hours_since_created": self.hours_since_created,
            "hours_since_access": self.hours_since_access,
            "contradicting_memory_ids": self.contradicting_memory_ids,
            "recommendation": self.recommendation,
        }


class StalenessDetector:
    """
    Detects stale memories based on multiple signals.

    Usage:
        detector = StalenessDetector(config)
        result = detector.check_staleness(memory_item, all_memories)
        if result.level in (StalenessLevel.STALE, StalenessLevel.EXPIRED):
            # Trigger refresh or removal
    """

    def __init__(self, config: Optional[StalenessConfig] = None):
        self.config = config or StalenessConfig()

    def check_staleness(
        self,
        memory_item: Dict[str, Any],
        all_memories: Optional[List[Dict[str, Any]]] = None,
        current_time: Optional[datetime] = None,
    ) -> StalenessResult:
        """
        Check if a memory is stale.

        Args:
            memory_item: Memory dict with at least 'id', 'created_at' keys
            all_memories: All memories for contradiction detection
            current_time: Override current time (for testing)

        Returns:
            StalenessResult with level, reason, and recommendation
        """
        now = current_time or datetime.now()
        memory_id = memory_item.get("id", "unknown")
        created_at = self._parse_timestamp(memory_item.get("created_at"))
        updated_at = self._parse_timestamp(memory_item.get("updated_at"))
        last_accessed = self._parse_timestamp(memory_item.get("last_accessed"))
        confidence = memory_item.get("score", memory_item.get("confidence", 1.0)) or 1.0

        hours_since_created = (now - created_at).total_seconds() / 3600 if created_at else 0
        hours_since_access = (now - last_accessed).total_seconds() / 3600 if last_accessed else hours_since_created

        # Check 1: TTL-based staleness
        ttl_result = self._check_ttl(hours_since_created, hours_since_access, confidence)
        if ttl_result:
            return ttl_result

        # Check 2: Confidence decay
        decay_result = self._check_confidence_decay(memory_id, confidence, hours_since_created)
        if decay_result:
            return decay_result

        # Check 3: Never accessed
        if not last_accessed and hours_since_created > self.config.never_accessed_ttl_hours:
            return StalenessResult(
                memory_id=memory_id,
                level=StalenessLevel.AGING,
                reason=StalenessReason.NEVER_ACCESSED,
                confidence=confidence,
                decayed_confidence=confidence,
                hours_since_created=hours_since_created,
                hours_since_access=hours_since_access,
                recommendation="Memory has never been accessed. Consider verifying or removing.",
            )

        # Check 4: Contradiction detection
        if self.config.enable_contradiction_detection and all_memories:
            contradiction_result = self._check_contradictions(memory_id, memory_item, all_memories, now)
            if contradiction_result:
                return contradiction_result

        # Memory is fresh
        return StalenessResult(
            memory_id=memory_id,
            level=StalenessLevel.FRESH,
            confidence=confidence,
            decayed_confidence=confidence,
            hours_since_created=hours_since_created,
            hours_since_access=hours_since_access,
            recommendation="Memory is current. No action needed.",
        )

    def check_batch_staleness(
        self,
        memories: List[Dict[str, Any]],
        current_time: Optional[datetime] = None,
    ) -> List[StalenessResult]:
        """Check staleness for multiple memories at once."""
        results = []
        for memory in memories:
            result = self.check_staleness(memory, memories, current_time)
            results.append(result)
        return results

    def get_stale_memories(
        self,
        memories: List[Dict[str, Any]],
        include_aging: bool = False,
    ) -> List[Tuple[Dict[str, Any], StalenessResult]]:
        """
        Filter memories to find stale (and optionally aging) ones.

        Returns:
            List of (memory, staleness_result) tuples
        """
        stale = []
        for memory in memories:
            result = self.check_staleness(memory, memories)
            if result.level == StalenessLevel.EXPIRED:
                stale.append((memory, result))
            elif include_aging and result.level in (
                StalenessLevel.STALE,
                StalenessLevel.AGING,
            ):
                stale.append((memory, result))
        return stale

    def _check_ttl(
        self,
        hours_since_created: float,
        hours_since_access: float,
        confidence: float,
    ) -> Optional[StalenessResult]:
        """Check if memory has exceeded its TTL."""
        # Determine TTL based on confidence
        if confidence >= 0.9:
            ttl = self.config.high_confidence_ttl_hours
        elif confidence <= 0.5:
            ttl = self.config.low_confidence_ttl_hours
        else:
            ttl = self.config.default_ttl_hours

        if hours_since_created > ttl:
            return StalenessResult(
                memory_id="unknown",
                level=StalenessLevel.EXPIRED,
                reason=StalenessReason.TTL_EXPIRED,
                confidence=confidence,
                decayed_confidence=max(0, confidence - 0.5),
                hours_since_created=hours_since_created,
                hours_since_access=hours_since_access,
                recommendation=f"Memory TTL expired ({hours_since_created:.0f}h > {ttl:.0f}h). Remove or refresh.",
            )

        return None

    def _check_confidence_decay(
        self,
        memory_id: str,
        confidence: float,
        hours_since_created: float,
    ) -> Optional[StalenessResult]:
        """Check if confidence has decayed below threshold."""
        days_since_created = hours_since_created / 24
        decayed_confidence = confidence * (1 - self.config.confidence_decay_rate) ** days_since_created

        if decayed_confidence < self.config.min_confidence_threshold:
            return StalenessResult(
                memory_id=memory_id,
                level=StalenessLevel.STALE,
                reason=StalenessReason.CONFIDENCE_DECAY,
                confidence=confidence,
                decayed_confidence=decayed_confidence,
                hours_since_created=hours_since_created,
                hours_since_access=hours_since_created,
                recommendation=f"Confidence decayed from {confidence:.2f} to {decayed_confidence:.2f}. Verify or remove.",
            )

        # Check if approaching staleness
        decay_ratio = decayed_confidence / self.config.min_confidence_threshold
        if decay_ratio < 1.5:
            return StalenessResult(
                memory_id=memory_id,
                level=StalenessLevel.AGING,
                reason=StalenessReason.CONFIDENCE_DECAY,
                confidence=confidence,
                decayed_confidence=decayed_confidence,
                hours_since_created=hours_since_created,
                hours_since_access=hours_since_created,
                recommendation=f"Confidence approaching threshold ({decayed_confidence:.2f} / {self.config.min_confidence_threshold:.2f}). Monitor closely.",
            )

        return None

    def _check_contradictions(
        self,
        memory_id: str,
        memory_item: Dict[str, Any],
        all_memories: List[Dict[str, Any]],
        current_time: datetime,
    ) -> Optional[StalenessResult]:
        """
        Detect if newer memories contradict this memory.
        Simple heuristic: check for overlapping keywords with opposite sentiment.
        """
        memory_text = memory_item.get("memory", "").lower()
        created_at = self._parse_timestamp(memory_item.get("created_at"))
        if not created_at or not memory_text:
            return None

        time_window = timedelta(hours=self.config.contradiction_time_window_hours)

        contradicting_ids = []
        for other in all_memories:
            if other.get("id") == memory_id:
                continue

            other_created = self._parse_timestamp(other.get("created_at"))
            if not other_created:
                continue

            # Only check newer memories within time window
            if other_created <= created_at:
                continue
            if other_created - created_at > time_window:
                continue

            other_text = other.get("memory", "").lower()

            # Simple contradiction heuristic: shared keywords with negation
            if self._has_contradiction(memory_text, other_text):
                contradicting_ids.append(other.get("id", "unknown"))

        if contradicting_ids:
            return StalenessResult(
                memory_id=memory_id,
                level=StalenessLevel.STALE,
                reason=StalenessReason.CONTRADICTION,
                confidence=memory_item.get("score", 1.0),
                decayed_confidence=memory_item.get("score", 1.0) * 0.5,
                hours_since_created=(current_time - created_at).total_seconds() / 3600,
                hours_since_access=0,
                contradicting_memory_ids=contradicting_ids,
                recommendation=f"Possible contradiction with {len(contradicting_ids)} newer memories. Review needed.",
            )

        return None

    def _has_contradiction(self, text1: str, text2: str) -> bool:
        """
        Simple contradiction detection based on keyword overlap with negation.
        A more sophisticated version would use NLI models.
        """
        negation_words = {
            "not",
            "no",
            "never",
            "don't",
            "doesn't",
            "didn't",
            "won't",
            "wouldn't",
            "shouldn't",
            "can't",
            "cannot",
        }

        words1 = set(text1.split())
        words2 = set(text2.split())

        # Check for significant overlap
        overlap = words1 & words2
        if len(overlap) < 2:
            return False

        # Check if one has negation that the other doesn't
        has_negation1 = bool(words1 & negation_words)
        has_negation2 = bool(words2 & negation_words)

        if has_negation1 != has_negation2:
            # One is negated, the other isn't - possible contradiction
            return True

        return False

    def _parse_timestamp(self, ts) -> Optional[datetime]:
        """Parse various timestamp formats."""
        if ts is None:
            return None
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, str):
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(ts, fmt)
                except ValueError:
                    continue
        return None

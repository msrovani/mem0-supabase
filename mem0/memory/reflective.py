"""
Meta-Cognitive Reflection - Phase 4.3
Origin: Meta-cognitive reflection in memory agents
        Memory for Autonomous LLM Agents (arXiv:2603.07670)
        Ego & Reflection layers in mem0-supabase 12-layer architecture

This module implements a reflective loop that periodically analyzes
its own memory actions and adjusts strategies:
- Pattern analysis of memory operations
- Self-critique and revision
- Proactive improvement suggestions
- Memory quality assessment
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ReflectionType(str, Enum):
    """Types of reflection."""

    PATTERN_ANALYSIS = "pattern_analysis"
    QUALITY_ASSESSMENT = "quality_assessment"
    STRATEGY_REVISION = "strategy_revision"
    CONTRADICTION_DETECTION = "contradiction_detection"
    GAP_IDENTIFICATION = "gap_identification"


@dataclass
class ReflectionInsight:
    """A single insight from reflection."""

    reflection_type: ReflectionType
    insight: str
    confidence: float
    severity: str  # "low", "medium", "high", "critical"
    recommendation: str
    affected_memory_ids: List[str]
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reflection_type": self.reflection_type.value,
            "insight": self.insight,
            "confidence": self.confidence,
            "severity": self.severity,
            "recommendation": self.recommendation,
            "affected_memory_ids": self.affected_memory_ids,
            "timestamp": self.timestamp,
        }


@dataclass
class ReflectionReport:
    """Complete reflection report."""

    insights: List[ReflectionInsight]
    overall_quality_score: float
    total_memories_analyzed: int
    reflection_duration_ms: float
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "insights": [i.to_dict() for i in self.insights],
            "overall_quality_score": self.overall_quality_score,
            "total_memories_analyzed": self.total_memories_analyzed,
            "reflection_duration_ms": self.reflection_duration_ms,
            "timestamp": self.timestamp,
            "summary": f"Analyzed {self.total_memories_analyzed} memories, "
            f"found {len(self.insights)} insights, "
            f"quality score: {self.overall_quality_score:.2f}",
        }


class MetaCognitiveReflector:
    """
    Meta-cognitive reflection engine for memory self-improvement.

    Usage:
        reflector = MetaCognitiveReflector()
        report = reflector.reflect(memory_history, current_memories)
        for insight in report.insights:
            print(f"[{insight.severity}] {insight.insight}")
    """

    def __init__(
        self,
        min_quality_score: float = 0.6,
        max_contradiction_age_hours: float = 168.0,  # 7 days
        enable_pattern_analysis: bool = True,
        enable_quality_assessment: bool = True,
        enable_gap_identification: bool = True,
    ):
        self.min_quality_score = min_quality_score
        self.max_contradiction_age_hours = max_contradiction_age_hours
        self.enable_pattern_analysis = enable_pattern_analysis
        self.enable_quality_assessment = enable_quality_assessment
        self.enable_gap_identification = enable_gap_identification
        self._reflection_history: List[ReflectionReport] = []

    def reflect(
        self,
        memory_history: List[Dict[str, Any]],
        current_memories: List[Dict[str, Any]],
        llm_client: Any = None,
    ) -> ReflectionReport:
        """
        Perform a full meta-cognitive reflection.

        Args:
            memory_history: Log of memory operations (add, update, delete, access)
            current_memories: Current state of all memories
            llm_client: Optional LLM for deeper analysis

        Returns:
            ReflectionReport with insights and quality score
        """
        import time

        start = time.monotonic()
        insights: List[ReflectionInsight] = []

        # 1. Pattern Analysis
        if self.enable_pattern_analysis:
            insights.extend(self._analyze_patterns(memory_history))

        # 2. Quality Assessment
        if self.enable_quality_assessment:
            insights.extend(self._assess_quality(current_memories))

        # 3. Contradiction Detection
        insights.extend(self._detect_contradictions(current_memories))

        # 4. Gap Identification
        if self.enable_gap_identification:
            insights.extend(self._identify_gaps(current_memories, memory_history))

        # 5. Strategy Revision (if LLM available)
        if llm_client:
            insights.extend(self._suggest_strategy_revisions(insights, llm_client))

        # Calculate overall quality score
        quality_score = self._calculate_quality_score(current_memories, insights)

        elapsed_ms = (time.monotonic() - start) * 1000

        report = ReflectionReport(
            insights=insights,
            overall_quality_score=quality_score,
            total_memories_analyzed=len(current_memories),
            reflection_duration_ms=elapsed_ms,
            timestamp=datetime.now().isoformat(),
        )

        self._reflection_history.append(report)
        logger.info(
            f"Reflection complete: {len(insights)} insights, quality={quality_score:.2f}, duration={elapsed_ms:.0f}ms"
        )

        return report

    def _analyze_patterns(self, history: List[Dict[str, Any]]) -> List[ReflectionInsight]:
        """Analyze patterns in memory operations."""
        insights = []

        if not history:
            return insights

        # Pattern 1: High deletion rate
        deletes = [h for h in history if h.get("action") == "delete"]
        adds = [h for h in history if h.get("action") == "add"]
        if adds and len(deletes) / len(adds) > 0.5:
            insights.append(
                ReflectionInsight(
                    reflection_type=ReflectionType.PATTERN_ANALYSIS,
                    insight=f"High deletion rate: {len(deletes)} deletes vs {len(adds)} adds ({len(deletes) / len(adds):.0%})",
                    confidence=0.9,
                    severity="high",
                    recommendation="Review memory ingestion criteria. Too many memories are being created and then deleted.",
                    affected_memory_ids=[],
                    timestamp=datetime.now().isoformat(),
                )
            )

        # Pattern 2: Low access rate
        accesses = [h for h in history if h.get("action") == "access"]
        if adds and len(accesses) / len(adds) < 0.2:
            insights.append(
                ReflectionInsight(
                    reflection_type=ReflectionType.PATTERN_ANALYSIS,
                    insight=f"Low access rate: only {len(accesses)} accesses for {len(adds)} memories ({len(accesses) / len(adds):.0%})",
                    confidence=0.85,
                    severity="medium",
                    recommendation="Most memories are never accessed. Consider stricter ingestion filters or better retrieval.",
                    affected_memory_ids=[],
                    timestamp=datetime.now().isoformat(),
                )
            )

        # Pattern 3: Burst creation
        if len(adds) > 10:
            timestamps = []
            for h in adds:
                try:
                    ts = datetime.fromisoformat(h.get("timestamp", ""))
                    timestamps.append(ts)
                except (ValueError, TypeError):
                    pass

            if len(timestamps) > 5:
                timestamps.sort()
                time_span = (timestamps[-1] - timestamps[0]).total_seconds()
                if time_span > 0 and len(timestamps) / (time_span / 3600) > 50:
                    insights.append(
                        ReflectionInsight(
                            reflection_type=ReflectionType.PATTERN_ANALYSIS,
                            insight=f"Burst creation: {len(timestamps)} memories in {time_span / 3600:.1f} hours ({len(timestamps) / (time_span / 3600):.0f}/hr)",
                            confidence=0.8,
                            severity="medium",
                            recommendation="Memory creation is bursty. Consider rate limiting or batch processing.",
                            affected_memory_ids=[],
                            timestamp=datetime.now().isoformat(),
                        )
                    )

        return insights

    def _assess_quality(self, memories: List[Dict[str, Any]]) -> List[ReflectionInsight]:
        """Assess the quality of current memories."""
        insights = []

        if not memories:
            return insights

        # Low quality memories
        low_quality = [m for m in memories if m.get("score", m.get("confidence", 1.0)) < 0.4]
        if low_quality:
            ids = [m.get("id", "unknown") for m in low_quality]
            insights.append(
                ReflectionInsight(
                    reflection_type=ReflectionType.QUALITY_ASSESSMENT,
                    insight=f"{len(low_quality)} memories ({len(low_quality) / len(memories):.0%}) have low quality scores (<0.4)",
                    confidence=0.95,
                    severity="high",
                    recommendation=f"Review and potentially remove {len(low_quality)} low-quality memories.",
                    affected_memory_ids=ids[:20],  # Limit to first 20
                    timestamp=datetime.now().isoformat(),
                )
            )

        # Very long memories (might be too verbose)
        long_memories = [m for m in memories if len(m.get("memory", "")) > 500]
        if long_memories:
            ids = [m.get("id", "unknown") for m in long_memories]
            insights.append(
                ReflectionInsight(
                    reflection_type=ReflectionType.QUALITY_ASSESSMENT,
                    insight=f"{len(long_memories)} memories are very long (>500 chars), may need summarization",
                    confidence=0.7,
                    severity="low",
                    recommendation="Consider summarizing long memories for token efficiency.",
                    affected_memory_ids=ids[:20],
                    timestamp=datetime.now().isoformat(),
                )
            )

        return insights

    def _detect_contradictions(self, memories: List[Dict[str, Any]]) -> List[ReflectionInsight]:
        """Detect contradictions among memories."""
        insights = []
        contradictions = self._find_contradicting_pairs(memories)

        if contradictions:
            affected = []
            for m1, m2 in contradictions[:5]:
                affected.extend([m1.get("id", "unknown"), m2.get("id", "unknown")])

            insights.append(
                ReflectionInsight(
                    reflection_type=ReflectionType.CONTRADICTION_DETECTION,
                    insight=f"Found {len(contradictions)} pairs of potentially contradictory memories",
                    confidence=0.75,
                    severity="high",
                    recommendation="Review contradictory memories and resolve conflicts. Keep the most recent/accurate version.",
                    affected_memory_ids=affected,
                    timestamp=datetime.now().isoformat(),
                )
            )

        return insights

    def _find_contradicting_pairs(self, memories: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """Find pairs of memories that may contradict each other."""
        contradictions = []
        negation_words = {"not", "no", "never", "don't", "doesn't", "didn't", "won't", "can't", "cannot"}

        for i, m1 in enumerate(memories):
            text1 = m1.get("memory", "").lower()
            words1 = set(text1.split())
            has_negation1 = bool(words1 & negation_words)

            for m2 in memories[i + 1 :]:
                text2 = m2.get("memory", "").lower()
                words2 = set(text2.split())
                has_negation2 = bool(words2 & negation_words)

                # Check for contradiction: similar content but different negation
                overlap = len(words1 & words2)
                if overlap >= 3 and has_negation1 != has_negation2:
                    contradictions.append((m1, m2))

        return contradictions

    def _identify_gaps(
        self,
        memories: List[Dict[str, Any]],
        history: List[Dict[str, Any]],
    ) -> List[ReflectionInsight]:
        """Identify gaps in memory coverage."""
        insights = []

        # Gap 1: No recent memories
        now = datetime.now()
        recent_cutoff = now - timedelta(days=7)
        recent = []
        for m in memories:
            try:
                created = datetime.fromisoformat(m.get("created_at", ""))
                if created > recent_cutoff:
                    recent.append(m)
            except (ValueError, TypeError):
                pass

        if not recent and memories:
            insights.append(
                ReflectionInsight(
                    reflection_type=ReflectionType.GAP_IDENTIFICATION,
                    insight="No memories created in the last 7 days",
                    confidence=0.8,
                    severity="medium",
                    recommendation="Memory system may not be actively capturing new information.",
                    affected_memory_ids=[],
                    timestamp=datetime.now().isoformat(),
                )
            )

        # Gap 2: Missing memory types
        types_found = set(m.get("type", "unknown") for m in memories)
        expected_types = {"episodic", "semantic", "procedural"}
        missing = expected_types - types_found
        if missing and len(memories) > 5:
            insights.append(
                ReflectionInsight(
                    reflection_type=ReflectionType.GAP_IDENTIFICATION,
                    insight=f"Missing memory types: {', '.join(missing)}",
                    confidence=0.7,
                    severity="low",
                    recommendation=f"Consider capturing {', '.join(missing)} memories for more complete coverage.",
                    affected_memory_ids=[],
                    timestamp=datetime.now().isoformat(),
                )
            )

        return insights

    def _suggest_strategy_revisions(
        self,
        current_insights: List[ReflectionInsight],
        llm_client: Any,
    ) -> List[ReflectionInsight]:
        """Use LLM to suggest strategy revisions based on current insights."""
        if not current_insights:
            return []

        insights_summary = "\n".join(f"- [{i.severity}] {i.insight}" for i in current_insights)
        prompt = f"""Based on these memory system insights, suggest 2-3 specific strategy improvements:

{insights_summary}

Format each suggestion as:
- Strategy: [name]
- Change: [what to change]
- Expected impact: [benefit]
"""

        try:
            response = llm_client.generate(prompt)
            return [
                ReflectionInsight(
                    reflection_type=ReflectionType.STRATEGY_REVISION,
                    insight=response[:500],
                    confidence=0.6,
                    severity="medium",
                    recommendation="Review and implement suggested strategy changes.",
                    affected_memory_ids=[],
                    timestamp=datetime.now().isoformat(),
                )
            ]
        except Exception as e:
            logger.error(f"LLM strategy suggestion failed: {e}")
            return []

    def _calculate_quality_score(
        self,
        memories: List[Dict[str, Any]],
        insights: List[ReflectionInsight],
    ) -> float:
        """Calculate overall memory quality score (0.0 to 1.0)."""
        if not memories:
            return 0.0

        # Base score from memory scores
        avg_score = sum(m.get("score", m.get("confidence", 0.5)) for m in memories) / len(memories)

        # Penalty for insights
        severity_penalties = {"low": 0.02, "medium": 0.05, "high": 0.1, "critical": 0.2}
        total_penalty = sum(severity_penalties.get(i.severity, 0.05) for i in insights)

        return max(0.0, min(1.0, avg_score - total_penalty))

    def get_reflection_history(self, limit: int = 10) -> List[ReflectionReport]:
        """Get recent reflection reports."""
        return self._reflection_history[-limit:]

    def get_quality_trend(self) -> List[Dict[str, Any]]:
        """Get quality score trend over time."""
        return [
            {"timestamp": r.timestamp, "quality_score": r.overall_quality_score, "insights_count": len(r.insights)}
            for r in self._reflection_history
        ]

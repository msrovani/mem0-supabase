"""
Application-Level Memory Evaluation - Phase 3.4
Origin: LOCOMO Benchmark (arXiv:2504.19413), LoCoMo-Plus (arXiv:2602.10715)
        https://github.com/xjtuleeyf/Locomo-Plus

Evaluation harness for memory quality:
- Accuracy: How correct are retrieved memories?
- Latency: How fast is retrieval?
- Token Efficiency: How many tokens used?
- Staleness Rate: What % of served memories are stale?
"""

import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Result of a single evaluation run."""

    test_name: str
    accuracy: float  # 0.0 to 1.0
    avg_latency_ms: float
    avg_token_count: float
    staleness_rate: float  # 0.0 to 1.0
    total_tests: int
    passed_tests: int
    timestamp: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "accuracy": round(self.accuracy, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "avg_token_count": round(self.avg_token_count, 1),
            "staleness_rate": round(self.staleness_rate, 4),
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "timestamp": self.timestamp,
            **self.details,
        }

    def summary(self) -> str:
        return (
            f"Test: {self.test_name}\n"
            f"  Accuracy: {self.accuracy:.1%} ({self.passed_tests}/{self.total_tests})\n"
            f"  Avg Latency: {self.avg_latency_ms:.1f}ms\n"
            f"  Avg Tokens: {self.avg_token_count:.0f}\n"
            f"  Staleness Rate: {self.staleness_rate:.1%}"
        )


@dataclass
class EvaluationReport:
    """Complete evaluation report."""

    results: List[EvaluationResult]
    overall_score: float
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "results": [r.to_dict() for r in self.results],
            "overall_score": round(self.overall_score, 4),
            "timestamp": self.timestamp,
            "summary": self.generate_summary(),
        }

    def generate_summary(self) -> str:
        lines = [f"Memory Evaluation Report - {self.timestamp}", f"Overall Score: {self.overall_score:.2f}/1.00", ""]
        for r in self.results:
            lines.append(r.summary())
            lines.append("")
        return "\n".join(lines)


class MemoryEvaluator:
    """
    Evaluates memory system quality across multiple dimensions.

    Usage:
        evaluator = MemoryEvaluator(memory_system)
        report = evaluator.run_evaluation(test_cases, ground_truth)
        print(report.generate_summary())
    """

    def __init__(
        self,
        memory_system: Any = None,
        staleness_detector: Any = None,
    ):
        self.memory_system = memory_system
        self.staleness_detector = staleness_detector

    def run_evaluation(
        self,
        test_cases: List[Dict[str, Any]],
        ground_truth: List[Dict[str, Any]],
    ) -> EvaluationReport:
        """
        Run full evaluation suite.

        Args:
            test_cases: List of {"query": str, "expected_memory_ids": List[str]}
            ground_truth: List of {"memory_id": str, "content": str, "is_correct": bool}

        Returns:
            EvaluationReport with all metrics
        """
        results = []

        # Test 1: Retrieval Accuracy
        accuracy_result = self._evaluate_accuracy(test_cases, ground_truth)
        results.append(accuracy_result)

        # Test 2: Latency
        latency_result = self._evaluate_latency(test_cases)
        results.append(latency_result)

        # Test 3: Token Efficiency
        token_result = self._evaluate_token_efficiency(test_cases)
        results.append(token_result)

        # Test 4: Staleness Rate
        staleness_result = self._evaluate_staleness(ground_truth)
        results.append(staleness_result)

        # Calculate overall score (weighted average)
        weights = {"accuracy": 0.4, "latency": 0.25, "token_efficiency": 0.2, "staleness": 0.15}
        latency_score = max(0, 1.0 - (latency_result.avg_latency_ms / 1000))  # Target <1000ms
        token_score = max(0, 1.0 - (token_result.avg_token_count / 5000))  # Target <5000 tokens

        overall = (
            accuracy_result.accuracy * weights["accuracy"]
            + latency_score * weights["latency"]
            + token_score * weights["token_efficiency"]
            + (1.0 - staleness_result.staleness_rate) * weights["staleness"]
        )

        return EvaluationReport(
            results=results,
            overall_score=overall,
            timestamp=datetime.now().isoformat(),
        )

    def _evaluate_accuracy(
        self,
        test_cases: List[Dict[str, Any]],
        ground_truth: List[Dict[str, Any]],
    ) -> EvaluationResult:
        """Evaluate retrieval accuracy."""
        if not test_cases or not self.memory_system:
            return EvaluationResult(
                test_name="Retrieval Accuracy",
                accuracy=0.0,
                avg_latency_ms=0,
                avg_token_count=0,
                staleness_rate=0,
                total_tests=0,
                passed_tests=0,
                timestamp=datetime.now().isoformat(),
            )

        gt_map = {gt["memory_id"]: gt for gt in ground_truth}
        passed = 0
        latencies = []

        for tc in test_cases:
            start = time.monotonic()
            try:
                results = self.memory_system.search(tc["query"], limit=5)
                result_ids = {r.get("id") for r in results} if results else set()
                expected = set(tc.get("expected_memory_ids", []))

                # Check if any expected memory was retrieved
                if result_ids & expected:
                    passed += 1
            except Exception as e:
                logger.error(f"Accuracy test error: {e}")

            latencies.append((time.monotonic() - start) * 1000)

        total = len(test_cases)
        return EvaluationResult(
            test_name="Retrieval Accuracy",
            accuracy=passed / total if total > 0 else 0.0,
            avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
            avg_token_count=0,
            staleness_rate=0,
            total_tests=total,
            passed_tests=passed,
            timestamp=datetime.now().isoformat(),
        )

    def _evaluate_latency(self, test_cases: List[Dict[str, Any]]) -> EvaluationResult:
        """Evaluate retrieval latency."""
        latencies = []

        if not self.memory_system:
            return EvaluationResult(
                test_name="Latency",
                accuracy=0,
                avg_latency_ms=0,
                avg_token_count=0,
                staleness_rate=0,
                total_tests=0,
                passed_tests=0,
                timestamp=datetime.now().isoformat(),
            )

        for tc in test_cases[:20]:  # Sample
            start = time.monotonic()
            try:
                self.memory_system.search(tc["query"], limit=5)
            except Exception:
                pass
            latencies.append((time.monotonic() - start) * 1000)

        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        passed = sum(1 for l in latencies if l < 500)  # Target <500ms

        return EvaluationResult(
            test_name="Latency",
            accuracy=passed / len(latencies) if latencies else 0,
            avg_latency_ms=avg_latency,
            avg_token_count=0,
            staleness_rate=0,
            total_tests=len(latencies),
            passed_tests=passed,
            timestamp=datetime.now().isoformat(),
            details={"p50_ms": sorted(latencies)[len(latencies) // 2] if latencies else 0},
        )

    def _evaluate_token_efficiency(self, test_cases: List[Dict[str, Any]]) -> EvaluationResult:
        """Evaluate token efficiency of retrieved memories."""
        token_counts = []

        if not self.memory_system:
            return EvaluationResult(
                test_name="Token Efficiency",
                accuracy=0,
                avg_latency_ms=0,
                avg_token_count=0,
                staleness_rate=0,
                total_tests=0,
                passed_tests=0,
                timestamp=datetime.now().isoformat(),
            )

        for tc in test_cases[:20]:
            try:
                results = self.memory_system.search(tc["query"], limit=5)
                if results:
                    total_text = " ".join(r.get("memory", "") for r in results)
                    tokens = len(total_text.split())
                    token_counts.append(tokens)
            except Exception:
                pass

        avg_tokens = sum(token_counts) / len(token_counts) if token_counts else 0
        passed = sum(1 for t in token_counts if t < 2000)  # LOCOMO target: ~1.8k tokens

        return EvaluationResult(
            test_name="Token Efficiency",
            accuracy=passed / len(token_counts) if token_counts else 0,
            avg_latency_ms=0,
            avg_token_count=avg_tokens,
            staleness_rate=0,
            total_tests=len(token_counts),
            passed_tests=passed,
            timestamp=datetime.now().isoformat(),
        )

    def _evaluate_staleness(self, ground_truth: List[Dict[str, Any]]) -> EvaluationResult:
        """Evaluate staleness rate of memories."""
        if not self.staleness_detector or not ground_truth:
            return EvaluationResult(
                test_name="Staleness Rate",
                accuracy=0,
                avg_latency_ms=0,
                avg_token_count=0,
                staleness_rate=0,
                total_tests=0,
                passed_tests=0,
                timestamp=datetime.now().isoformat(),
            )

        stale_count = 0
        for gt in ground_truth:
            result = self.staleness_detector.check_staleness(gt)
            if result.level.value in ("stale", "expired"):
                stale_count += 1

        total = len(ground_truth)
        staleness_rate = stale_count / total if total > 0 else 0

        return EvaluationResult(
            test_name="Staleness Rate",
            accuracy=1.0 - staleness_rate,
            avg_latency_ms=0,
            avg_token_count=0,
            staleness_rate=staleness_rate,
            total_tests=total,
            passed_tests=total - stale_count,
            timestamp=datetime.now().isoformat(),
        )

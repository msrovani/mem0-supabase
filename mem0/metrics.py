"""
Prometheus Metrics — /metrics endpoint for Mem0 API.

Exports:
- mem0_requests_total: Total HTTP requests by method/path/status
- mem0_request_duration_seconds: Request latency histogram
- mem0_memory_operations_total: Memory CRUD operations
- mem0_cache_hits_total: Cache hit/miss counters
- mem0_circuit_breaker_state: Circuit breaker states
- mem0_active_connections: Current active connections
"""

from __future__ import annotations

import threading
import time
from typing import Dict, Optional

__all__ = ["MetricsRegistry", "metrics"]


class _Counter:
    """Simple Prometheus-style counter."""
    def __init__(self):
        self._values: Dict[str, float] = {}
        self._lock = threading.Lock()

    def inc(self, labels: Optional[Dict[str, str]] = None, value: float = 1.0) -> None:
        key = ",".join(f"{k}={v}" for k, v in sorted((labels or {}).items()))
        with self._lock:
            self._values[key] = self._values.get(key, 0) + value

    def render(self, name: str, help_text: str, label_names: str) -> str:
        lines = [f"# HELP {name} {help_text}", f"# TYPE {name} counter"]
        with self._lock:
            for labels, value in self._values.items():
                if labels:
                    lines.append(f'{name}{{{label_names}="{labels}"}} {value}')
                else:
                    lines.append(f"{name} {value}")
        return "\n".join(lines)


class _Histogram:
    """Simple Prometheus-style histogram."""
    def __init__(self, buckets=None):
        self._buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        self._counts: Dict[str, int] = {}
        self._sum: Dict[str, float] = {}
        self._lock = threading.Lock()

    def observe(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        key = ",".join(f"{k}={v}" for k, v in sorted((labels or {}).items()))
        with self._lock:
            self._sum[key] = self._sum.get(key, 0.0) + value
            for b in self._buckets:
                if value <= b:
                    bucket_key = f"{key},le={b}"
                    self._counts[bucket_key] = self._counts.get(bucket_key, 0) + 1
            # +Inf bucket
            inf_key = f"{key},le=+Inf"
            self._counts[inf_key] = self._counts.get(inf_key, 0) + 1

    def render(self, name: str, help_text: str) -> str:
        lines = [f"# HELP {name} {help_text}", f"# TYPE {name} histogram"]
        with self._lock:
            for key, count in sorted(self._counts.items()):
                lines.append(f'{name}_bucket{{{key}}} {count}')
            for key, total in sorted(self._sum.items()):
                lines.append(f'{name}_sum{{{key}}} {total}')
                lines.append(f'{name}_count{{{key}}} {self._counts.get(key + ",le=+Inf", 0)}')
        return "\n".join(lines)


class _Gauge:
    """Simple Prometheus-style gauge."""
    def __init__(self):
        self._values: Dict[str, float] = {}
        self._lock = threading.Lock()

    def set(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        key = ",".join(f"{k}={v}" for k, v in sorted((labels or {}).items()))
        with self._lock:
            self._values[key] = value

    def render(self, name: str, help_text: str) -> str:
        lines = [f"# HELP {name} {help_text}", f"# TYPE {name} gauge"]
        with self._lock:
            for labels, value in self._values.items():
                if labels:
                    lines.append(f'{name}{{{labels}}} {value}')
                else:
                    lines.append(f"{name} {value}")
        return "\n".join(lines)


class MetricsRegistry:
    """
    Prometheus-compatible metrics registry.

    Usage:
        from mem0.metrics import metrics
        metrics.http_requests.inc(labels={"method": "POST", "path": "/memories", "status": "200"})
        metrics.http_requests_duration.observe(0.123, labels={"method": "POST"})
        print(metrics.render())
    """

    def __init__(self):
        self.http_requests = _Counter()
        self.http_requests_duration = _Histogram()
        self.memory_operations = _Counter()
        self.cache_hits = _Counter()
        self.circuit_breaker_state = _Gauge()
        self.active_connections = _Gauge()
        self.start_time = time.time()

    def render(self) -> str:
        """Render all metrics in Prometheus text format."""
        sections = [
            self.http_requests.render("mem0_requests_total", "Total HTTP requests", "labels"),
            self.http_requests_duration.render("mem0_request_duration_seconds", "Request duration in seconds"),
            self.memory_operations.render("mem0_memory_operations_total", "Memory CRUD operations", "labels"),
            self.cache_hits.render("mem0_cache_hits_total", "Cache hit/miss counters", "labels"),
            self.circuit_breaker_state.render("mem0_circuit_breaker_state", "Circuit breaker state (0=closed, 1=open, 2=half_open)"),
            self.active_connections.render("mem0_active_connections", "Active connections"),
            f"# HELP mem0_uptime_seconds Uptime in seconds\n# TYPE mem0_uptime_seconds gauge\nmem0_uptime_seconds {time.time() - self.start_time:.1f}",
        ]
        return "\n\n".join(sections) + "\n"


# Global singleton
metrics = MetricsRegistry()

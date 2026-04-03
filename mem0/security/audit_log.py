"""
Audit Logging - Structured Security Event Logging

Provides production-ready audit logging for all security-relevant events
in the mem0-supabase system. Supports file rotation, async logging,
severity filtering, and automatic retention policy.
"""

import json
import os
import queue
import threading
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

__all__ = [
    "EventType",
    "AuditEvent",
    "AuditLogger",
    "get_audit_logger",
    "log_event",
]

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Standard audit event types."""

    AUTH_FAILURE = "AUTH_FAILURE"
    AUTH_SUCCESS = "AUTH_SUCCESS"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    MEMORY_ACCESS = "MEMORY_ACCESS"
    MEMORY_CREATE = "MEMORY_CREATE"
    MEMORY_DELETE = "MEMORY_DELETE"
    MEMORY_UPDATE = "MEMORY_UPDATE"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    PII_REDACTION = "PII_REDACTION"
    SECURITY_SCAN = "SECURITY_SCAN"
    SYSTEM_STARTUP = "SYSTEM_STARTUP"
    SYSTEM_SHUTDOWN = "SYSTEM_SHUTDOWN"


class _Severity(str, Enum):
    """Internal severity levels."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


_SEVERITY_ORDER = {_Severity.INFO: 0, _Severity.WARNING: 1, _Severity.CRITICAL: 2}


@dataclass(slots=True)
class AuditEvent:
    """A single audit log event."""

    timestamp: str
    event_type: str
    actor: str
    source_ip: str
    resource_type: str
    resource_id: str
    action: str
    severity: str
    details: Dict[str, Any] = field(default_factory=dict)
    request_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))


class AuditLogger:
    """
    Thread-safe audit logger with rotation, async support, and retention policy.

    Usage:
        logger = get_audit_logger()
        logger.log_event(
            EventType.AUTH_FAILURE,
            actor="user123",
            action="login_attempt",
            source_ip="203.0.113.5",
            resource_type="user",
            resource_id="user123",
            details={"reason": "invalid_password"},
            severity="WARNING",
        )
    """

    def __init__(
        self,
        log_file_path: Optional[str] = None,
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB
        backup_count: int = 5,
        min_severity: str = "INFO",
        use_async: bool = False,
        retention_days: int = 30,
        log_to_stdout: bool = True,
        log_to_file: bool = True,
    ):
        """
        Initialize the AuditLogger.

        Args:
            log_file_path: Path to the audit log file. If None, uses MEM0_AUDIT_LOG_FILE env var.
            max_bytes: Max file size before rotation (default 10MB).
            backup_count: Number of backup files to keep.
            min_severity: Minimum severity to log (INFO, WARNING, CRITICAL).
            use_async: Enable async logging via background thread.
            retention_days: Auto-delete logs older than N days.
            log_to_stdout: Also write to stdout.
            log_to_file: Write to file (requires log_file_path).
        """
        self._lock = threading.Lock()
        self._min_severity = _Severity(min_severity.upper())
        self._retention_days = retention_days
        self._log_to_stdout = log_to_stdout
        self._log_to_file = log_to_file
        self._file_path = log_file_path or os.environ.get("MEM0_AUDIT_LOG_FILE")

        # Async support
        self._use_async = use_async or os.environ.get("MEM0_AUDIT_LOG_ASYNC", "0") == "1"
        self._queue: Optional[queue.Queue] = None
        self._worker: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        if self._use_async:
            self._queue = queue.Queue(maxsize=0)  # unbounded
            self._worker = threading.Thread(target=self._worker_loop, daemon=True)
            self._worker.start()

        # File rotation setup (tracked manually since we use stdlib only)
        self._max_bytes = max_bytes
        self._backup_count = backup_count

        # Enforce retention on startup
        self._cleanup_old_logs()

    def log_event(
        self,
        event_type: str,
        actor: str,
        action: str,
        source_ip: str = "",
        resource_type: str = "",
        resource_id: str = "",
        severity: str = "INFO",
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """
        Log a security audit event.

        Args:
            event_type: One of EventType values.
            actor: User ID or "system".
            action: What action was taken.
            source_ip: Client IP address.
            resource_type: Type of resource affected.
            resource_id: ID of resource affected.
            severity: INFO, WARNING, or CRITICAL.
            details: Additional context dict.
            request_id: Optional request identifier for tracing.
        """
        sev = _Severity(severity.upper())
        if _SEVERITY_ORDER.get(sev, 0) < _SEVERITY_ORDER[self._min_severity]:
            return

        event = AuditEvent(
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            event_type=event_type,
            actor=actor,
            source_ip=source_ip,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            severity=severity.upper(),
            details=details or {},
            request_id=request_id,
        )

        if self._use_async and self._queue is not None:
            try:
                self._queue.put_nowait(event)
            except queue.Full:
                # Fallback to sync if queue is full (shouldn't happen with unbounded)
                self._emit(event)
        else:
            self._emit(event)

    def _emit(self, event: AuditEvent) -> None:
        """Write event to configured outputs (thread-safe)."""
        json_line = event.to_json()

        with self._lock:
            if self._log_to_stdout:
                print(json_line, flush=True)

            if self._log_to_file and self._file_path:
                self._write_to_file(json_line)

    def _write_to_file(self, json_line: str) -> None:
        """Write to file with manual rotation."""
        log_path = Path(self._file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if rotation needed
        if log_path.exists() and log_path.stat().st_size >= self._max_bytes:
            self._rotate_file(log_path)

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json_line + "\n")

    def _rotate_file(self, log_path: Path) -> None:
        """Rotate log file: rename current to .1, .2, etc."""
        for i in range(self._backup_count, 0, -1):
            src = Path(f"{log_path}.{i - 1}" if i > 1 else log_path)
            dst = Path(f"{log_path}.{i}")
            if src.exists():
                src.rename(dst)

    def _cleanup_old_logs(self) -> None:
        """Delete log files older than retention_days."""
        if not self._file_path:
            return
        log_path = Path(self._file_path)
        if not log_path.parent.exists():
            return

        import time

        cutoff = time.time() - (self._retention_days * 86400)

        for f in log_path.parent.glob(f"{log_path.name}*"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
            except OSError:
                pass

    def _worker_loop(self) -> None:
        """Background thread that drains the queue and emits events."""
        while not self._stop_event.is_set():
            try:
                event = self._queue.get(timeout=1.0)
                self._emit(event)
                self._queue.task_done()
            except queue.Empty:
                continue

    def stop(self) -> None:
        """Gracefully stop the async worker and flush remaining events."""
        if self._use_async and self._queue is not None:
            self._stop_event.set()
            # Drain remaining
            while True:
                try:
                    event = self._queue.get_nowait()
                    self._emit(event)
                except queue.Empty:
                    break
            if self._worker:
                self._worker.join(timeout=5)


# Singleton
_audit_logger: Optional[AuditLogger] = None
_audit_lock = threading.Lock()


def get_audit_logger(**config_overrides) -> AuditLogger:
    """
    Get or create the global AuditLogger singleton.

    Args:
        **config_overrides: Passed to AuditLogger constructor on first init.

    Returns:
        AuditLogger instance.
    """
    global _audit_logger
    if _audit_logger is None:
        with _audit_lock:
            if _audit_logger is None:
                _audit_logger = AuditLogger(**config_overrides)
    return _audit_logger


def log_event(
    event_type: str,
    actor: str,
    action: str,
    source_ip: str = "",
    resource_type: str = "",
    resource_id: str = "",
    severity: str = "INFO",
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> None:
    """
    Convenience function: log an event using the global audit logger.

    Args:
        event_type: One of EventType values.
        actor: User ID or "system".
        action: What action was taken.
        source_ip: Client IP address.
        resource_type: Type of resource affected.
        resource_id: ID of resource affected.
        severity: INFO, WARNING, or CRITICAL.
        details: Additional context dict.
        request_id: Optional request identifier.
    """
    get_audit_logger().log_event(
        event_type=event_type,
        actor=actor,
        action=action,
        source_ip=source_ip,
        resource_type=resource_type,
        resource_id=resource_id,
        severity=severity,
        details=details,
        request_id=request_id,
    )

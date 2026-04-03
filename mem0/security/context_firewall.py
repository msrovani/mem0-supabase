"""
ContextFirewall - PII Redaction Engine

Redacts sensitive information from text before it reaches LLMs or is returned
in API responses. Uses regex-based pattern matching for zero-latency redaction.
"""

import re
import threading
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RedactionResult:
    """Result of a PII redaction operation."""

    original_text: str
    redacted_text: str
    redactions_found: Dict[str, int] = field(default_factory=dict)

    @property
    def is_clean(self) -> bool:
        return sum(self.redactions_found.values()) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "redacted_text": self.redacted_text,
            "redactions_found": self.redactions_found,
            "is_clean": self.is_clean,
        }


# Default PII patterns
_DEFAULT_PATTERNS = [
    {
        "name": "EMAIL",
        "pattern": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "placeholder": "[EMAIL_REDACTED]",
        "enabled": True,
    },
    {
        "name": "CPF",
        "pattern": r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b",
        "placeholder": "[CPF_REDACTED]",
        "enabled": True,
    },
    {
        "name": "SSN",
        "pattern": r"\b\d{3}-\d{2}-\d{4}\b",
        "placeholder": "[SSN_REDACTED]",
        "enabled": True,
    },
    {
        "name": "CREDIT_CARD",
        "pattern": r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b",
        "placeholder": "[CREDIT_CARD_REDACTED]",
        "enabled": True,
    },
    {
        "name": "PHONE",
        "pattern": r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b",
        "placeholder": "[PHONE_REDACTED]",
        "enabled": True,
    },
    {
        "name": "IPV4",
        "pattern": r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
        "placeholder": "[IP_REDACTED]",
        "enabled": True,
    },
    {
        "name": "API_KEY",
        "pattern": r"\b(?:sk-[a-zA-Z0-9]{20,}|key_[a-zA-Z0-9]{10,}|token_[a-zA-Z0-9]{10,})\b",
        "placeholder": "[API_KEY_REDACTED]",
        "enabled": True,
    },
]


class ContextFirewall:
    """
    Production-ready PII redaction engine using regex patterns.

    Usage:
        firewall = ContextFirewall()
        result = firewall.redact_text("Contact user@example.com")
        print(result.redacted_text)  # "Contact [EMAIL_REDACTED]"

        # Batch processing
        results = firewall.redact_batch(["email: a@b.co", "ip: 192.168.1.1"])
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the ContextFirewall.

        Args:
            config: Optional configuration dict with:
                - custom_patterns: List of pattern dicts to add
                - disable: List of pattern names to disable
                - enable: List of pattern names to enable (if empty, all enabled)
        """
        self._lock = threading.Lock()
        self._total_redactions = 0
        self._patterns: List[Dict[str, Any]] = []
        self._compiled: List[tuple] = []

        self._load_patterns(config)

    def _load_patterns(self, config: Optional[Dict[str, Any]]) -> None:
        """Load and compile patterns based on config."""
        disable = set((config or {}).get("disable", []))
        enable = set((config or {}).get("enable", []))
        custom = (config or {}).get("custom_patterns", [])

        for p in _DEFAULT_PATTERNS:
            name = p["name"]
            if name in disable:
                continue
            if enable and name not in enable:
                continue
            self._patterns.append(p)

        for p in custom:
            if p.get("enabled", True) and p.get("name") and p.get("pattern"):
                self._patterns.append(p)

        self._compiled = [(p["name"], re.compile(p["pattern"]), p["placeholder"]) for p in self._patterns]

    def redact_text(
        self,
        text: str,
        disable: Optional[List[str]] = None,
        enable: Optional[List[str]] = None,
    ) -> RedactionResult:
        """
        Redact PII from a single text string.

        Args:
            text: Input text to redact.
            disable: Override - disable specific pattern names for this call.
            enable: Override - enable only these pattern names for this call.

        Returns:
            RedactionResult with redacted text and statistics.
        """
        if not text:
            return RedactionResult(original_text=text, redacted_text=text)

        disable_set = set(disable or [])
        enable_set = set(enable or [])

        redaction_counts: Dict[str, int] = {}
        redacted = text

        for name, regex, placeholder in self._compiled:
            if name in disable_set:
                continue
            if enable_set and name not in enable_set:
                continue

            matches = regex.findall(redacted)
            count = len(matches)
            if count > 0:
                redaction_counts[name] = count
                redacted = regex.sub(placeholder, redacted)

        total = sum(redaction_counts.values())
        with self._lock:
            self._total_redactions += total

        return RedactionResult(
            original_text=text,
            redacted_text=redacted,
            redactions_found=redaction_counts,
        )

    def redact_batch(
        self,
        texts: List[str],
        disable: Optional[List[str]] = None,
        enable: Optional[List[str]] = None,
    ) -> List[RedactionResult]:
        """
        Redact PII from multiple text strings.

        Args:
            texts: List of input texts.
            disable: Override - disable specific patterns.
            enable: Override - enable only these patterns.

        Returns:
            List of RedactionResult, one per input text.
        """
        return [self.redact_text(t, disable=disable, enable=enable) for t in texts]

    @property
    def total_redactions(self) -> int:
        """Total PII redactions performed across all calls (thread-safe)."""
        with self._lock:
            return self._total_redactions

    def get_active_patterns(self) -> List[str]:
        """Return list of currently active pattern names."""
        return [p["name"] for p in self._patterns]


# Global default instance for convenience
_default_firewall: Optional[ContextFirewall] = None
_firewall_lock = threading.Lock()


def get_firewall(config: Optional[Dict[str, Any]] = None) -> ContextFirewall:
    """Get or create the global ContextFirewall singleton."""
    global _default_firewall
    if _default_firewall is None:
        with _firewall_lock:
            if _default_firewall is None:
                _default_firewall = ContextFirewall(config)
    return _default_firewall


def redact_text(text: str, **config_overrides) -> RedactionResult:
    """
    Convenience function: redact PII using the global firewall.

    Args:
        text: Input text to redact.
        **config_overrides: Passed to firewall.redact_text() (disable, enable).

    Returns:
        RedactionResult with redacted text and statistics.
    """
    return get_firewall().redact_text(text, **config_overrides)

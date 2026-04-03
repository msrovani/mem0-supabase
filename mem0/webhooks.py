"""
Webhook System — Event-driven notifications for memory events.

Notifies external systems when memories are created, updated, deleted,
or when security events occur. Supports HTTP POST with retry and signature verification.

Usage:
    from mem0.webhooks import WebhookManager

    hooks = WebhookManager()
    hooks.register("https://my-app.com/webhook", events=["memory.create", "memory.delete"])
    hooks.emit("memory.create", {"memory_id": "123", "user_id": "u1"})
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

__all__ = ["WebhookManager", "WebhookSubscription"]


@dataclass
class WebhookSubscription:
    """A single webhook subscription."""

    url: str
    events: List[str]
    secret: Optional[str] = None
    active: bool = True
    max_retries: int = 3
    timeout: float = 10.0
    created_at: float = field(default_factory=time.time)
    last_triggered: Optional[float] = None
    failure_count: int = 0


class WebhookManager:
    """
    Manages webhook subscriptions and event emission.

    Thread-safe. Supports synchronous and async-compatible emission.
    """

    def __init__(self, signing_secret: Optional[str] = None):
        """
        Initialize WebhookManager.

        Args:
            signing_secret: Global secret for HMAC signature verification.
        """
        self._subscriptions: List[WebhookSubscription] = []
        self._lock = threading.Lock()
        self._signing_secret = signing_secret
        self._event_history: List[Dict[str, Any]] = []
        self._max_history = 1000

    def register(
        self,
        url: str,
        events: List[str],
        secret: Optional[str] = None,
        max_retries: int = 3,
        timeout: float = 10.0,
    ) -> WebhookSubscription:
        """
        Register a new webhook subscription.

        Args:
            url: Endpoint URL to POST events to.
            events: List of event types to subscribe to.
            secret: Per-subscription signing secret (optional).
            max_retries: Retry attempts on failure.
            timeout: HTTP request timeout in seconds.

        Returns:
            The created WebhookSubscription.
        """
        sub = WebhookSubscription(
            url=url,
            events=events,
            secret=secret,
            max_retries=max_retries,
            timeout=timeout,
        )
        with self._lock:
            self._subscriptions.append(sub)
        logger.info(f"Webhook registered: {url} for events {events}")
        return sub

    def unregister(self, url: str) -> bool:
        """
        Remove a webhook subscription by URL.

        Args:
            url: The webhook URL to remove.

        Returns:
            True if found and removed, False otherwise.
        """
        with self._lock:
            before = len(self._subscriptions)
            self._subscriptions = [s for s in self._subscriptions if s.url != url]
            removed = before - len(self._subscriptions) > 0
        if removed:
            logger.info(f"Webhook unregistered: {url}")
        return removed

    def emit(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Emit an event to all matching webhook subscriptions.

        Args:
            event_type: Event type string (e.g., "memory.create").
            payload: Event payload dict.

        Returns:
            Dict with delivery results per subscription.
        """
        event = {
            "id": f"evt_{int(time.time() * 1000)}",
            "type": event_type,
            "timestamp": time.time(),
            "payload": payload,
        }

        # Record in history
        with self._lock:
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history = self._event_history[-self._max_history :]

        results = {}
        matching_subs = self._get_matching_subs(event_type)

        for sub in matching_subs:
            results[sub.url] = self._deliver(sub, event)

        return results

    def _get_matching_subs(self, event_type: str) -> List[WebhookSubscription]:
        """Get subscriptions matching the event type."""
        with self._lock:
            return [s for s in self._subscriptions if s.active and (event_type in s.events or "*" in s.events)]

    def _deliver(self, sub: WebhookSubscription, event: Dict[str, Any]) -> Dict[str, Any]:
        """Deliver event to a single webhook with retry."""
        body = json.dumps(event).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event["type"],
            "X-Webhook-ID": event["id"],
        }

        # Add HMAC signature
        secret = sub.secret or self._signing_secret
        if secret:
            signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        last_error = None
        for attempt in range(sub.max_retries):
            try:
                req = Request(sub.url, data=body, headers=headers, method="POST")
                with urlopen(req, timeout=sub.timeout) as resp:
                    if resp.status < 300:
                        sub.last_triggered = time.time()
                        sub.failure_count = 0
                        return {"status": "delivered", "http_status": resp.status}
                    last_error = f"HTTP {resp.status}"
            except (HTTPError, URLError, OSError) as e:
                last_error = str(e)
                if attempt < sub.max_retries - 1:
                    time.sleep(min(2**attempt * 0.5, 10))

        sub.failure_count += 1
        # Deactivate after 10 consecutive failures
        if sub.failure_count >= 10:
            sub.active = False
            logger.warning(f"Webhook deactivated after 10 failures: {sub.url}")

        return {"status": "failed", "error": last_error, "attempts": sub.max_retries}

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent emitted events."""
        with self._lock:
            return list(self._event_history[-limit:])

    def get_stats(self) -> Dict[str, Any]:
        """Get webhook system statistics."""
        with self._lock:
            active = sum(1 for s in self._subscriptions if s.active)
            inactive = len(self._subscriptions) - active
            failing = sum(1 for s in self._subscriptions if s.failure_count > 0)

        return {
            "total_subscriptions": len(self._subscriptions),
            "active": active,
            "inactive": inactive,
            "failing": failing,
            "events_emitted": len(self._event_history),
        }

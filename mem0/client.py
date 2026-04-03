"""
Mem0 Python Client — Official SDK for the Mem0 Memory API.

Usage:
    from mem0_client import Mem0Client

    client = Mem0Client(base_url="http://localhost:8000", api_key="your-key")

    # Create memories
    result = client.add("User likes pizza", user_id="user1")

    # Search
    results = client.search("food preferences", user_id="user1")

    # Get all
    memories = client.get_all(user_id="user1")

    # Delete
    client.delete(memory_id="mem_123")
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

__version__ = "2.0.0"
__all__ = ["Mem0Client", "Mem0Error"]


class Mem0Error(Exception):
    """Base exception for Mem0 client errors."""
    def __init__(self, message: str, status_code: int = 0, response: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class Mem0Client:
    """
    Synchronous HTTP client for the Mem0 Memory API.

    Args:
        base_url: API base URL (default: http://localhost:8000).
        api_key: JWT token for authentication (optional).
        timeout: Request timeout in seconds (default: 30).
        retries: Number of retries on failure (default: 3).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.retries = retries
        self._session_headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if api_key:
            self._session_headers["Authorization"] = f"Bearer {api_key}"

    def _request(self, method: str, path: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make an HTTP request with retry logic."""
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8") if data else None

        last_error = None
        for attempt in range(self.retries):
            try:
                req = Request(url, data=body, headers=self._session_headers, method=method)
                with urlopen(req, timeout=self.timeout) as resp:
                    if resp.status >= 400:
                        raise Mem0Error(
                            f"API error: {resp.status}",
                            status_code=resp.status,
                        )
                    content = resp.read().decode("utf-8")
                    return json.loads(content) if content else {}
            except HTTPError as e:
                last_error = Mem0Error(f"HTTP {e.code}: {e.reason}", status_code=e.code)
                if e.code >= 500 and attempt < self.retries - 1:
                    import time
                    time.sleep(2 ** attempt * 0.5)
                    continue
                raise last_error
            except (URLError, OSError) as e:
                last_error = Mem0Error(f"Connection error: {e}")
                if attempt < self.retries - 1:
                    import time
                    time.sleep(2 ** attempt * 0.5)
                    continue
                raise last_error

        raise last_error or Mem0Error("Request failed after retries")

    # ============================================
    # Core Operations
    # ============================================

    def add(
        self,
        messages,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add new memories.

        Args:
            messages: String, dict, or list of message dicts.
            user_id: User identifier.
            agent_id: Agent identifier.
            run_id: Run/session identifier.
            metadata: Additional metadata.
            idempotency_key: Unique key for idempotent requests.

        Returns:
            API response dict.
        """
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        elif isinstance(messages, dict):
            messages = [messages]

        data = {
            "messages": messages,
            "user_id": user_id,
            "agent_id": agent_id,
            "run_id": run_id,
            "metadata": metadata,
            "idempotency_key": idempotency_key,
        }
        return self._request("POST", "/memories", data={k: v for k, v in data.items() if v is not None})

    def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Search memories.

        Args:
            query: Search query.
            user_id: Filter by user.
            agent_id: Filter by agent.
            run_id: Filter by run.
            filters: Additional filters.

        Returns:
            Search results dict.
        """
        data = {
            "query": query,
            "user_id": user_id,
            "agent_id": agent_id,
            "run_id": run_id,
            "filters": filters,
        }
        return self._request("POST", "/search", data={k: v for k, v in data.items() if v is not None})

    def get(self, memory_id: str) -> Dict[str, Any]:
        """Get a specific memory by ID."""
        return self._request("GET", f"/memories/{memory_id}")

    def get_all(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Get all memories with pagination.

        Returns:
            Dict with items, next_cursor, total_count.
        """
        params = {"user_id": user_id, "agent_id": agent_id, "run_id": run_id, "cursor": cursor, "limit": limit}
        query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        return self._request("GET", f"/memories?{query}" if query else "/memories")

    def update(self, memory_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a memory."""
        return self._request("PUT", f"/memories/{memory_id}", data=data)

    def delete(self, memory_id: str) -> Dict[str, Any]:
        """Delete a specific memory."""
        return self._request("DELETE", f"/memories/{memory_id}")

    def delete_all(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Delete all memories for an identifier."""
        params = {"user_id": user_id, "agent_id": agent_id, "run_id": run_id}
        query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        return self._request("DELETE", f"/memories?{query}" if query else "/memories")

    def history(self, memory_id: str) -> Dict[str, Any]:
        """Get memory history."""
        return self._request("GET", f"/memories/{memory_id}/history")

    def reset(self) -> Dict[str, Any]:
        """Reset all memories."""
        return self._request("POST", "/reset")

    def health(self) -> Dict[str, Any]:
        """Check API health."""
        return self._request("GET", "/health")

    def configure(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Update server configuration."""
        return self._request("POST", "/configure", data=config)

    def bulk_add(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Bulk add memories (up to 100).

        Args:
            items: List of memory create dicts.

        Returns:
            Dict with created, errors, results, error_details.
        """
        return self._request("POST", "/memories/bulk", data={"items": items})

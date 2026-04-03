"""
Redis Pub/Sub Integration — Real-time memory sync between Mem0 instances.

Enables multiple Mem0 API instances to share memory events in real-time.

Usage:
    from mem0.redis_pubsub import RedisPubSubManager

    pubsub = RedisPubSubManager(redis_url="redis://localhost:6379")
    pubsub.subscribe("memories", on_message)
    pubsub.publish("memories", {"event": "memory.create", "memory_id": "123"})
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

__all__ = ["RedisPubSubManager"]


class RedisPubSubManager:
    """
    Manages Redis pub/sub for real-time memory event broadcasting.

    Thread-safe. Supports multiple channels and message handlers.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """
        Initialize RedisPubSubManager.

        Args:
            redis_url: Redis connection URL.
        """
        self.redis_url = redis_url
        self._pub_client = None
        self._sub_client = None
        self._handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {}
        self._listener_thread: Optional[threading.Thread] = None
        self._running = False

    def _get_pub_client(self):
        """Get or create the publish client."""
        if self._pub_client is None:
            import redis
            self._pub_client = redis.from_url(self.redis_url, decode_responses=True)
        return self._pub_client

    def _get_sub_client(self):
        """Get or create the subscribe client."""
        if self._sub_client is None:
            import redis
            self._sub_client = redis.from_url(self.redis_url, decode_responses=True)
        return self._sub_client

    def publish(self, channel: str, message: Dict[str, Any]) -> int:
        """
        Publish a message to a channel.

        Args:
            channel: Channel name.
            message: Message dict (will be JSON-encoded).

        Returns:
            Number of subscribers that received the message.
        """
        client = self._get_pub_client()
        payload = json.dumps(message)
        return client.publish(channel, payload)

    def subscribe(self, channel: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        """
        Subscribe to a channel with a message handler.

        Args:
            channel: Channel name.
            handler: Callable that receives decoded message dict.
        """
        self._handlers[channel] = handler

        if not self._running:
            self._start_listener()

    def _start_listener(self) -> None:
        """Start the background listener thread."""
        self._running = True
        self._listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listener_thread.start()
        logger.info(f"Redis pub/sub listener started for channels: {list(self._handlers.keys())}")

    def _listen_loop(self) -> None:
        """Background thread that listens for messages."""
        import redis

        sub = self._get_sub_client()
        pubsub = sub.pubsub()

        for channel in self._handlers:
            pubsub.subscribe(channel)

        try:
            for message in pubsub.listen():
                if not self._running:
                    break

                if message["type"] == "message":
                    channel = message["channel"]
                    handler = self._handlers.get(channel)
                    if handler:
                        try:
                            data = json.loads(message["data"])
                            handler(data)
                        except Exception as e:
                            logger.error(f"Error handling message on {channel}: {e}")
        except redis.ConnectionError as e:
            logger.error(f"Redis connection lost: {e}")
        finally:
            pubsub.unsubscribe()
            pubsub.close()

    def stop(self) -> None:
        """Stop the listener."""
        self._running = False
        if self._listener_thread:
            self._listener_thread.join(timeout=5)
        if self._pub_client:
            self._pub_client.close()
        if self._sub_client:
            self._sub_client.close()

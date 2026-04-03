"""
Voice Agent Memory Optimization - Phase 3.3
Origin: ElevenLabs + Mem0 integration (https://docs.mem0.ai/integrations/elevenlabs)
        LiveKit External Data (https://docs.livekit.io/agents/logic/external-data/)
        Latency targets: vector 10-50ms, graph 50-150ms, multi-strategy 100-600ms

This module provides memory optimization for voice agents:
- Async memory writes (non-blocking)
- Voice-specific metadata (tone, emotion, pauses)
- Low-latency retrieval targets (<100ms)
- Streaming context assembly
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class VoiceMetadata:
    """Metadata specific to voice interactions."""

    tone: Optional[str] = None  # e.g., "formal", "casual", "urgent"
    emotion: Optional[str] = None  # e.g., "happy", "frustrated", "neutral"
    speech_rate: Optional[float] = None  # words per minute
    pause_count: int = 0
    avg_pause_duration_ms: float = 0.0
    background_noise: Optional[str] = None
    language: str = "en"
    accent: Optional[str] = None
    call_duration_seconds: float = 0.0
    interruption_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tone": self.tone,
            "emotion": self.emotion,
            "speech_rate": self.speech_rate,
            "pause_count": self.pause_count,
            "avg_pause_duration_ms": self.avg_pause_duration_ms,
            "background_noise": self.background_noise,
            "language": self.language,
            "accent": self.accent,
            "call_duration_seconds": self.call_duration_seconds,
            "interruption_count": self.interruption_count,
        }


@dataclass
class VoiceContext:
    """Assembled context for voice agent responses."""

    memories: List[Dict[str, Any]] = field(default_factory=list)
    voice_metadata: Optional[VoiceMetadata] = None
    retrieval_latency_ms: float = 0.0
    token_count: int = 0
    is_streaming: bool = False

    def to_prompt(self, max_tokens: int = 2000) -> str:
        """Convert context to a prompt-friendly string."""
        parts = []
        current_tokens = 0

        for memory in self.memories:
            mem_text = memory.get("memory", "")
            estimated_tokens = len(mem_text.split()) * 1.3  # rough estimate
            if current_tokens + estimated_tokens > max_tokens:
                break
            parts.append(f"- {mem_text}")
            current_tokens += estimated_tokens

        self.token_count = int(current_tokens)
        return "\n".join(parts)


class VoiceMemoryManager:
    """
    Manages memory for voice agents with latency optimization.

    Usage:
        manager = VoiceMemoryManager(memory_store)
        context = await manager.get_voice_context(user_id, max_latency_ms=100)
        await manager.store_voice_memory(transcript, voice_metadata)
    """

    def __init__(
        self,
        memory_store: Any = None,
        max_retrieval_latency_ms: float = 100.0,
        enable_async_writes: bool = True,
    ):
        self.memory_store = memory_store
        self.max_retrieval_latency_ms = max_retrieval_latency_ms
        self.enable_async_writes = enable_async_writes
        self._write_queue: asyncio.Queue = asyncio.Queue()
        self._write_task: Optional[asyncio.Task] = None
        self._latency_history: List[float] = []

    async def start(self):
        """Start the async write processor."""
        if self.enable_async_writes and self._write_task is None:
            self._write_task = asyncio.create_task(self._process_write_queue())

    async def stop(self):
        """Stop the async write processor."""
        if self._write_task:
            self._write_task.cancel()
            try:
                await self._write_task
            except asyncio.CancelledError:
                pass
            self._write_task = None

    async def get_voice_context(
        self,
        user_id: str,
        query: str = "",
        max_latency_ms: Optional[float] = None,
        max_memories: int = 5,
    ) -> VoiceContext:
        """
        Retrieve voice-optimized context within latency budget.

        Args:
            user_id: The user to retrieve context for
            query: Optional query to filter memories
            max_latency_ms: Maximum allowed retrieval latency (default: 100ms)
            max_memories: Maximum number of memories to retrieve

        Returns:
            VoiceContext with memories and metadata
        """
        start_time = time.monotonic()
        target_latency = max_latency_ms or self.max_retrieval_latency_ms

        context = VoiceContext()

        if self.memory_store is None:
            return context

        try:
            # Fast retrieval with timeout
            if query:
                memories = self.memory_store.search(query, user_id=user_id, limit=max_memories)
            else:
                memories = self.memory_store.get_recent(user_id, limit=max_memories)

            elapsed_ms = (time.monotonic() - start_time) * 1000
            context.memories = memories or []
            context.retrieval_latency_ms = elapsed_ms

            self._latency_history.append(elapsed_ms)
            if len(self._latency_history) > 100:
                self._latency_history = self._latency_history[-100:]

            if elapsed_ms > target_latency:
                logger.warning(f"Voice retrieval exceeded latency budget: {elapsed_ms:.1f}ms > {target_latency:.1f}ms")

        except Exception as e:
            logger.error(f"Voice context retrieval error: {e}")
            context.retrieval_latency_ms = (time.monotonic() - start_time) * 1000

        return context

    async def store_voice_memory(
        self,
        transcript: str,
        voice_metadata: Optional[VoiceMetadata] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """
        Store voice memory asynchronously (non-blocking).

        Args:
            transcript: The conversation transcript
            voice_metadata: Voice-specific metadata
            user_id: User identifier
            session_id: Session identifier
        """
        memory_data = {
            "transcript": transcript,
            "voice_metadata": voice_metadata.to_dict() if voice_metadata else {},
            "user_id": user_id,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
        }

        if self.enable_async_writes:
            await self._write_queue.put(memory_data)
        else:
            self._write_memory_sync(memory_data)

    async def _process_write_queue(self):
        """Process the async write queue."""
        while True:
            try:
                memory_data = await self._write_queue.get()
                self._write_memory_sync(memory_data)
                self._write_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Async voice memory write error: {e}")

    def _write_memory_sync(self, memory_data: Dict[str, Any]):
        """Synchronous memory write (used by async processor)."""
        if self.memory_store is None:
            return

        try:
            self.memory_store.add(
                messages=[{"role": "user", "content": memory_data["transcript"]}],
                user_id=memory_data.get("user_id"),
                metadata=memory_data.get("voice_metadata", {}),
            )
        except Exception as e:
            logger.error(f"Voice memory write error: {e}")

    def get_latency_stats(self) -> Dict[str, float]:
        """Get retrieval latency statistics."""
        if not self._latency_history:
            return {"avg_ms": 0, "p50_ms": 0, "p95_ms": 0, "p99_ms": 0}

        sorted_latencies = sorted(self._latency_history)
        n = len(sorted_latencies)

        return {
            "avg_ms": round(sum(sorted_latencies) / n, 2),
            "p50_ms": round(sorted_latencies[int(n * 0.5)], 2),
            "p95_ms": round(sorted_latencies[int(n * 0.95)], 2),
            "p99_ms": round(sorted_latencies[min(int(n * 0.99), n - 1)], 2),
            "total_retrievals": n,
        }

    def get_context_for_streaming(
        self,
        user_id: str,
        max_tokens: int = 1000,
    ) -> VoiceContext:
        """
        Get context optimized for streaming responses.
        Returns context that fits within token budget for low-latency streaming.
        """
        context = VoiceContext(is_streaming=True)

        if self.memory_store is None:
            return context

        try:
            memories = self.memory_store.get_recent(user_id, limit=3)
            context.memories = memories or []
            context.to_prompt(max_tokens=max_tokens)
        except Exception as e:
            logger.error(f"Streaming context error: {e}")

        return context

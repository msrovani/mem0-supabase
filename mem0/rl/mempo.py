"""
MemPO Policy Optimization - Phase 4.1
Origin: arXiv:2603.00680 - Self-Memory Policy Optimization for Long-Horizon Agents
        https://github.com/TheNewBeeKing/MemPO

This module implements a policy for memory management decisions:
- When to store vs. skip a memory
- When to evict old memories
- When to consolidate/merge memories
- Memory budget management

Includes both a rule-based policy (production-ready) and an RL-based policy scaffold.
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class MemoryAction(str, Enum):
    """Actions the memory policy can take."""

    STORE = "store"  # Store the memory
    SKIP = "skip"  # Don't store (redundant/unimportant)
    EVICT = "evict"  # Remove old memory
    CONSOLIDATE = "consolidate"  # Merge with existing memory
    ARCHIVE = "archive"  # Move to long-term storage
    REFRESH = "refresh"  # Update timestamp/boost importance


@dataclass
class MemoryContext:
    """Context for a memory management decision."""

    memory_text: str = ""
    memory_score: float = 0.5
    memory_age_hours: float = 0.0
    memory_access_count: int = 0
    current_memory_count: int = 0
    memory_budget_used: float = 0.0  # 0.0 to 1.0
    similar_memories: int = 0
    user_importance: float = 0.5
    recency_weight: float = 0.3
    is_conversation_turn: bool = False
    session_length_minutes: float = 0.0


@dataclass
class PolicyDecision:
    """Result of a policy decision."""

    action: MemoryAction
    confidence: float = 0.0
    reasoning: str = ""
    target_memory_id: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class RuleBasedMemoryPolicy:
    """
    Rule-based policy for memory management decisions.
    This is the production-ready fallback for the RL-based policy.
    """

    def __init__(
        self,
        max_memories: int = 1000,
        budget_threshold: float = 0.8,  # Trigger eviction at 80% budget
        min_store_score: float = 0.3,  # Minimum score to store
        consolidation_threshold: float = 0.85,  # Similarity threshold for consolidation
        eviction_min_access_count: int = 2,  # Don't evict frequently accessed memories
        archive_after_hours: float = 720.0,  # Archive after 30 days
    ):
        self.max_memories = max_memories
        self.budget_threshold = budget_threshold
        self.min_store_score = min_store_score
        self.consolidation_threshold = consolidation_threshold
        self.eviction_min_access_count = eviction_min_access_count
        self.archive_after_hours = archive_after_hours
        self._decision_history: List[Tuple[MemoryAction, float]] = []

    def decide(self, context: MemoryContext) -> PolicyDecision:
        """Make a memory management decision."""
        # Rule 1: Skip low-importance memories
        if context.memory_score < self.min_store_score:
            return PolicyDecision(
                action=MemoryAction.SKIP,
                confidence=0.9,
                reasoning=f"Memory score {context.memory_score:.2f} below threshold {self.min_store_score}",
            )

        # Rule 2: Consolidate if very similar memories exist
        if context.similar_memories > 0 and context.memory_score >= self.consolidation_threshold:
            return PolicyDecision(
                action=MemoryAction.CONSOLIDATE,
                confidence=0.8,
                reasoning=f"{context.similar_memories} similar memories exist, consolidate",
            )

        # Rule 3: Evict if budget is high
        if context.memory_budget_used >= self.budget_threshold:
            return PolicyDecision(
                action=MemoryAction.EVICT,
                confidence=0.85,
                reasoning=f"Budget used {context.memory_budget_used:.0%}, eviction needed",
            )

        # Rule 4: Archive old, rarely accessed memories
        if (
            context.memory_age_hours > self.archive_after_hours
            and context.memory_access_count < self.eviction_min_access_count
        ):
            return PolicyDecision(
                action=MemoryAction.ARCHIVE,
                confidence=0.75,
                reasoning=f"Memory is {context.memory_age_hours:.0f}h old with {context.memory_access_count} accesses",
            )

        # Rule 5: Refresh frequently accessed memories
        if context.memory_access_count >= 10 and context.memory_age_hours > 24:
            return PolicyDecision(
                action=MemoryAction.REFRESH,
                confidence=0.7,
                reasoning=f"Memory accessed {context.memory_access_count} times, refresh importance",
            )

        # Default: Store
        return PolicyDecision(
            action=MemoryAction.STORE,
            confidence=0.6,
            reasoning="No special conditions met, store normally",
        )

    def decide_batch(self, contexts: List[MemoryContext]) -> List[PolicyDecision]:
        """Make decisions for multiple memories at once."""
        return [self.decide(ctx) for ctx in contexts]

    def record_feedback(self, action: MemoryAction, reward: float):
        """Record feedback for policy improvement (for future RL integration)."""
        self._decision_history.append((action, reward))
        if len(self._decision_history) > 10000:
            self._decision_history = self._decision_history[-10000:]

    def get_stats(self) -> Dict[str, Any]:
        """Get policy statistics."""
        action_counts = {}
        avg_rewards = {}
        for action, reward in self._decision_history:
            action_counts[action.value] = action_counts.get(action.value, 0) + 1
            if action.value not in avg_rewards:
                avg_rewards[action.value] = []
            avg_rewards[action.value].append(reward)

        avg_reward_by_action = {k: round(sum(v) / len(v), 4) for k, v in avg_rewards.items()}

        return {
            "total_decisions": len(self._decision_history),
            "action_distribution": action_counts,
            "average_reward_by_action": avg_reward_by_action,
        }


class RLMemoryPolicy(RuleBasedMemoryPolicy):
    """
    RL-based memory policy (scaffold for future training).
    Extends the rule-based policy with learned decision-making.

    TODO: Integrate with actual RL framework (stable-baselines3, Ray RLlib)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._model = None
        self._training_data: List[Dict[str, Any]] = []

    def decide(self, context: MemoryContext) -> PolicyDecision:
        """Make a decision using the RL model (or fallback to rules)."""
        if self._model is None:
            # Fallback to rule-based policy
            return super().decide(context)

        # TODO: Implement RL model inference
        # state = self._context_to_state(context)
        # action_idx = self._model.predict(state)
        # return self._action_idx_to_decision(action_idx, context)
        return super().decide(context)

    def update_policy(self, feedback: List[Dict[str, Any]]):
        """
        Update the policy based on feedback.
        In production, this would trigger RL training.
        """
        self._training_data.extend(feedback)
        logger.info(f"Policy updated with {len(feedback)} feedback entries (total: {len(self._training_data)})")

        # TODO: Trigger RL training when enough data accumulated
        # if len(self._training_data) >= self.training_batch_size:
        #     self._train_model()

    def _context_to_state(self, context: MemoryContext) -> List[float]:
        """Convert memory context to RL state vector."""
        return [
            context.memory_score,
            context.memory_age_hours / 1000.0,  # Normalize
            context.memory_access_count / 100.0,
            context.current_memory_count / 1000.0,
            context.memory_budget_used,
            context.similar_memories / 10.0,
            context.user_importance,
        ]

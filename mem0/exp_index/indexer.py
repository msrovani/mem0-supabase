"""
Memex(RL) Experience Indexing - Phase 3.2
Origin: arXiv:2603.04257 - Scaling Long-Horizon LLM Agents via Indexed Experience Memory

This module indexes long-horizon agent experiences (trajectories, events, outcomes)
for efficient recall and planning. It enables agents to learn from past experiences
and apply them to new situations.

Key concepts:
- Experience: A complete trajectory of actions and outcomes
- Index: Organized retrieval structure for experiences
- Chain: Linked experiences that form a sequence
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class OutcomeType(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    UNKNOWN = "unknown"


class Experience:
    """A single indexed experience (trajectory + outcome)."""

    def __init__(
        self,
        task_description: str,
        trajectory: List[Dict[str, Any]],
        outcome: OutcomeType,
        outcome_description: str = "",
        context: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        duration_seconds: float = 0.0,
        steps_count: int = 0,
    ):
        self.id = str(uuid.uuid4())
        self.task_description = task_description
        self.trajectory = trajectory  # List of {action, observation, thought}
        self.outcome = outcome
        self.outcome_description = outcome_description
        self.context = context or {}
        self.tags = tags or []
        self.user_id = user_id
        self.duration_seconds = duration_seconds
        self.steps_count = steps_count or len(trajectory)
        self.created_at = datetime.now().isoformat()
        self.retrieval_count = 0
        self.success_score = self._compute_success_score()

    def _compute_success_score(self) -> float:
        if self.outcome == OutcomeType.SUCCESS:
            return 1.0
        elif self.outcome == OutcomeType.PARTIAL:
            return 0.5
        elif self.outcome == OutcomeType.FAILURE:
            return 0.0
        return 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "task_description": self.task_description,
            "trajectory": self.trajectory,
            "outcome": self.outcome.value,
            "outcome_description": self.outcome_description,
            "context": self.context,
            "tags": self.tags,
            "user_id": self.user_id,
            "duration_seconds": self.duration_seconds,
            "steps_count": self.steps_count,
            "created_at": self.created_at,
            "retrieval_count": self.retrieval_count,
            "success_score": self.success_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Experience":
        return cls(
            task_description=data["task_description"],
            trajectory=data.get("trajectory", []),
            outcome=OutcomeType(data.get("outcome", "unknown")),
            outcome_description=data.get("outcome_description", ""),
            context=data.get("context", {}),
            tags=data.get("tags", []),
            user_id=data.get("user_id"),
            duration_seconds=data.get("duration_seconds", 0.0),
            steps_count=data.get("steps_count", 0),
        )


class ExperienceIndexer:
    """
    Indexes and retrieves experiences for long-horizon agent learning.

    Usage:
        indexer = ExperienceIndexer()
        exp_id = indexer.index_experience(
            task_description="Deploy web application",
            trajectory=[{"action": "build", "observation": "..."}],
            outcome=OutcomeType.SUCCESS,
        )
        similar = indexer.search_similar_experiences("deploy app")
    """

    def __init__(self):
        self._experiences: Dict[str, Experience] = {}
        self._index_by_task: Dict[str, List[str]] = {}  # keyword -> [exp_ids]
        self._index_by_outcome: Dict[str, List[str]] = {}  # outcome -> [exp_ids]
        self._index_by_tag: Dict[str, List[str]] = {}  # tag -> [exp_ids]
        self._chains: Dict[str, List[str]] = {}  # chain_id -> [exp_ids]
        self._exp_to_chain: Dict[str, str] = {}  # exp_id -> chain_id

    def index_experience(
        self,
        task_description: str,
        trajectory: List[Dict[str, Any]],
        outcome: OutcomeType,
        outcome_description: str = "",
        context: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        chain_id: Optional[str] = None,
    ) -> str:
        """Index a new experience."""
        exp = Experience(
            task_description=task_description,
            trajectory=trajectory,
            outcome=outcome,
            outcome_description=outcome_description,
            context=context,
            tags=tags,
            user_id=user_id,
            duration_seconds=context.get("duration_seconds", 0) if context else 0,
        )

        self._experiences[exp.id] = exp

        # Index by task keywords
        for word in task_description.lower().split():
            if len(word) > 2:  # Skip short words
                if word not in self._index_by_task:
                    self._index_by_task[word] = []
                self._index_by_task[word].append(exp.id)

        # Index by outcome
        outcome_key = outcome.value
        if outcome_key not in self._index_by_outcome:
            self._index_by_outcome[outcome_key] = []
        self._index_by_outcome[outcome_key].append(exp.id)

        # Index by tags
        for tag in tags or []:
            if tag not in self._index_by_tag:
                self._index_by_tag[tag] = []
            self._index_by_tag[tag].append(exp.id)

        # Link to chain if provided
        if chain_id:
            if chain_id not in self._chains:
                self._chains[chain_id] = []
            self._chains[chain_id].append(exp.id)
            self._exp_to_chain[exp.id] = chain_id

        logger.info(f"Indexed experience: {task_description} ({exp.id})")
        return exp.id

    def search_similar_experiences(
        self,
        query: str,
        outcome_filter: Optional[OutcomeType] = None,
        tag_filter: Optional[str] = None,
        min_success_score: float = 0.0,
        top_n: int = 10,
    ) -> List[Experience]:
        """Search for similar experiences."""
        query_words = set(query.lower().split())
        candidate_ids = set()

        # Find candidates by keyword overlap
        for word in query_words:
            if len(word) > 2 and word in self._index_by_task:
                candidate_ids.update(self._index_by_task[word])

        # Apply filters
        results = []
        for exp_id in candidate_ids:
            exp = self._experiences.get(exp_id)
            if exp is None:
                continue

            if outcome_filter and exp.outcome != outcome_filter:
                continue
            if tag_filter and tag_filter not in exp.tags:
                continue
            if exp.success_score < min_success_score:
                continue

            # Score by keyword overlap
            exp_words = set(exp.task_description.lower().split())
            overlap = len(query_words & exp_words)
            total = len(query_words | exp_words)
            score = overlap / total if total > 0 else 0.0

            # Boost by success score and retrieval count (popularity)
            final_score = score * 0.6 + exp.success_score * 0.3 + min(exp.retrieval_count * 0.01, 0.1)

            results.append((exp, final_score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)

        # Increment retrieval count
        for exp, _ in results[:top_n]:
            exp.retrieval_count += 1

        return [exp for exp, _ in results[:top_n]]

    def get_experience_chain(self, exp_id: str) -> List[Experience]:
        """Get the chain of experiences that this experience belongs to."""
        chain_id = self._exp_to_chain.get(exp_id)
        if not chain_id:
            exp = self._experiences.get(exp_id)
            return [exp] if exp else []

        return [self._experiences[eid] for eid in self._chains.get(chain_id, []) if eid in self._experiences]

    def get_successful_patterns(self, task_keywords: str) -> List[Dict[str, Any]]:
        """Extract successful patterns for a given task type."""
        experiences = self.search_similar_experiences(
            task_keywords,
            outcome_filter=OutcomeType.SUCCESS,
            min_success_score=0.8,
            top_n=20,
        )

        patterns = []
        for exp in experiences:
            # Extract the most common successful action sequence
            if exp.trajectory:
                first_actions = [step.get("action", "") for step in exp.trajectory[:3]]
                patterns.append(
                    {
                        "experience_id": exp.id,
                        "task": exp.task_description,
                        "first_actions": first_actions,
                        "outcome_description": exp.outcome_description,
                        "success_score": exp.success_score,
                    }
                )

        return patterns

    def delete_experience(self, exp_id: str) -> bool:
        """Delete an experience from the index."""
        if exp_id not in self._experiences:
            return False

        exp = self._experiences.pop(exp_id)

        # Remove from indexes
        for word in exp.task_description.lower().split():
            if word in self._index_by_task:
                self._index_by_task[word] = [eid for eid in self._index_by_task[word] if eid != exp_id]

        outcome_key = exp.outcome.value
        if outcome_key in self._index_by_outcome:
            self._index_by_outcome[outcome_key] = [eid for eid in self._index_by_outcome[outcome_key] if eid != exp_id]

        for tag in exp.tags:
            if tag in self._index_by_tag:
                self._index_by_tag[tag] = [eid for eid in self._index_by_tag[tag] if eid != exp_id]

        # Remove from chain
        chain_id = self._exp_to_chain.pop(exp_id, None)
        if chain_id and chain_id in self._chains:
            self._chains[chain_id] = [eid for eid in self._chains[chain_id] if eid != exp_id]

        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get experience index statistics."""
        by_outcome = {}
        for outcome in OutcomeType:
            by_outcome[outcome.value] = len(self._index_by_outcome.get(outcome.value, []))

        return {
            "total_experiences": len(self._experiences),
            "by_outcome": by_outcome,
            "total_chains": len(self._chains),
            "total_tags": len(self._index_by_tag),
            "avg_success_score": round(
                sum(e.success_score for e in self._experiences.values()) / max(len(self._experiences), 1),
                4,
            ),
        }

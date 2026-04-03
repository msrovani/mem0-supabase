"""
Identity Resolution Cross-Session - Phase 3.1
Origin: Mem0 Group-Chat v2 identity patterns, cross-session continuity research

This module resolves whether different sessions/interactions come from the same user,
enabling continuous memory across devices, auth methods, and sessions.

Features:
- Behavioral fingerprinting (writing patterns, topics, time patterns)
- Identity graph connecting multiple user_ids
- Session-to-canonical identity mapping
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class IdentityResolver:
    """
    Resolves cross-session user identity using behavioral signals.

    Usage:
        resolver = IdentityResolver()
        canonical_id = resolver.resolve_identity(session_data)
        resolver.link_identities("user-123", "anon-456")
    """

    def __init__(self, similarity_threshold: float = 0.7):
        self.similarity_threshold = similarity_threshold
        # Canonical ID -> set of linked IDs
        self._identity_graph: Dict[str, Set[str]] = {}
        # ID -> canonical ID mapping
        self._id_to_canonical: Dict[str, str] = {}
        # User ID -> behavioral profile
        self._profiles: Dict[str, Dict[str, Any]] = {}

    def resolve_identity(self, session_data: Dict[str, Any]) -> str:
        """
        Resolve the canonical identity for a session.

        Args:
            session_data: Dict with user_id, session_id, and behavioral signals
                - user_id: Known or anonymous user ID
                - writing_style: Dict with avg_word_length, sentence_length, etc.
                - common_topics: List of frequently discussed topics
                - active_hours: List of hours when user is typically active
                - language: Primary language used

        Returns:
            Canonical identity ID
        """
        user_id = session_data.get("user_id", session_data.get("session_id", "unknown"))

        # If already mapped, return canonical ID
        if user_id in self._id_to_canonical:
            return self._id_to_canonical[user_id]

        # Try to match against existing profiles
        best_match = self._find_best_match(session_data)
        if best_match:
            canonical_id, score = best_match
            if score >= self.similarity_threshold:
                self._link_to_canonical(user_id, canonical_id)
                self._update_profile(canonical_id, session_data)
                logger.info(f"Resolved identity: {user_id} -> {canonical_id} (score={score:.2f})")
                return canonical_id

        # Create new canonical identity
        canonical_id = f"identity-{uuid.uuid4().hex[:12]}"
        self._link_to_canonical(user_id, canonical_id)
        self._profiles[canonical_id] = self._extract_profile(session_data)
        logger.info(f"Created new identity: {canonical_id} for {user_id}")
        return canonical_id

    def link_identities(self, id1: str, id2: str) -> str:
        """
        Explicitly link two identities as the same user.

        Returns:
            The canonical identity ID
        """
        canonical1 = self._id_to_canonical.get(id1, id1)
        canonical2 = self._id_to_canonical.get(id2, id2)

        if canonical1 == canonical2:
            return canonical1

        # Merge smaller into larger
        if len(self._identity_graph.get(canonical1, {canonical1})) >= len(
            self._identity_graph.get(canonical2, {canonical2})
        ):
            target, source = canonical1, canonical2
        else:
            target, source = canonical2, canonical1

        # Merge profiles
        if source in self._profiles and target in self._profiles:
            self._profiles[target] = self._merge_profiles(self._profiles[target], self._profiles[source])
            del self._profiles[source]

        # Update graph
        if target not in self._identity_graph:
            self._identity_graph[target] = {target}
        if source in self._identity_graph:
            self._identity_graph[target].update(self._identity_graph[source])
            del self._identity_graph[source]
        self._identity_graph[target].add(source)

        # Update all mappings
        for linked_id in self._identity_graph[target]:
            self._id_to_canonical[linked_id] = target

        logger.info(f"Linked identities: {id1}, {id2} -> {target}")
        return target

    def get_canonical_identity(self, user_id: str) -> str:
        """Get the canonical identity for a user ID."""
        return self._id_to_canonical.get(user_id, user_id)

    def get_linked_identities(self, canonical_id: str) -> List[str]:
        """Get all IDs linked to a canonical identity."""
        return list(self._identity_graph.get(canonical_id, {canonical_id}))

    def get_profile(self, canonical_id: str) -> Optional[Dict[str, Any]]:
        """Get the behavioral profile for a canonical identity."""
        return self._profiles.get(canonical_id)

    def _find_best_match(self, session_data: Dict[str, Any]) -> Optional[Tuple[str, float]]:
        """Find the best matching existing profile."""
        best_score = 0.0
        best_match = None

        new_profile = self._extract_profile(session_data)

        for canonical_id, existing_profile in self._profiles.items():
            score = self._compute_similarity(new_profile, existing_profile)
            if score > best_score:
                best_score = score
                best_match = canonical_id

        return (best_match, best_score) if best_match else None

    def _extract_profile(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract a behavioral profile from session data."""
        return {
            "writing_style": session_data.get("writing_style", {}),
            "common_topics": set(session_data.get("common_topics", [])),
            "active_hours": set(session_data.get("active_hours", [])),
            "language": session_data.get("language", "unknown"),
            "avg_session_length": session_data.get("avg_session_length", 0),
            "preferred_tools": set(session_data.get("preferred_tools", [])),
        }

    def _compute_similarity(self, profile1: Dict[str, Any], profile2: Dict[str, Any]) -> float:
        """Compute similarity between two behavioral profiles."""
        scores = []

        # Language match (high weight)
        if profile1.get("language") and profile2.get("language"):
            lang_score = 1.0 if profile1["language"] == profile2["language"] else 0.0
            scores.append(lang_score * 1.5)

        # Topic overlap (Jaccard similarity)
        topics1 = profile1.get("common_topics", set())
        topics2 = profile2.get("common_topics", set())
        if topics1 and topics2:
            intersection = len(topics1 & topics2)
            union = len(topics1 | topics2)
            topic_score = intersection / union if union > 0 else 0.0
            scores.append(topic_score)

        # Active hours overlap
        hours1 = profile1.get("active_hours", set())
        hours2 = profile2.get("active_hours", set())
        if hours1 and hours2:
            intersection = len(hours1 & hours2)
            union = len(hours1 | hours2)
            hour_score = intersection / union if union > 0 else 0.0
            scores.append(hour_score * 0.8)

        # Writing style similarity
        style1 = profile1.get("writing_style", {})
        style2 = profile2.get("writing_style", {})
        if style1 and style2:
            style_scores = []
            for key in set(style1.keys()) & set(style2.keys()):
                v1, v2 = float(style1[key]), float(style2[key])
                if v1 + v2 > 0:
                    style_scores.append(1.0 - abs(v1 - v2) / (v1 + v2))
            if style_scores:
                scores.append(sum(style_scores) / len(style_scores))

        return sum(scores) / sum([1.5, 1.0, 0.8, 1.0][: len(scores)]) if scores else 0.0

    def _merge_profiles(self, profile1: Dict[str, Any], profile2: Dict[str, Any]) -> Dict[str, Any]:
        """Merge two behavioral profiles."""
        merged = dict(profile1)
        merged["common_topics"] = profile1.get("common_topics", set()) | profile2.get("common_topics", set())
        merged["active_hours"] = profile1.get("active_hours", set()) | profile2.get("active_hours", set())
        merged["preferred_tools"] = profile1.get("preferred_tools", set()) | profile2.get("preferred_tools", set())

        # Average writing style
        style1 = profile1.get("writing_style", {})
        style2 = profile2.get("writing_style", {})
        merged_style = {}
        for key in set(style1.keys()) | set(style2.keys()):
            v1, v2 = float(style1.get(key, 0)), float(style2.get(key, 0))
            merged_style[key] = (v1 + v2) / 2
        merged["writing_style"] = merged_style

        return merged

    def _update_profile(self, canonical_id: str, session_data: Dict[str, Any]):
        """Update an existing profile with new session data."""
        if canonical_id not in self._profiles:
            self._profiles[canonical_id] = self._extract_profile(session_data)
            return

        existing = self._profiles[canonical_id]
        new_profile = self._extract_profile(session_data)

        # Merge topics and hours
        existing["common_topics"] = existing.get("common_topics", set()) | new_profile.get("common_topics", set())
        existing["active_hours"] = existing.get("active_hours", set()) | new_profile.get("active_hours", set())
        existing["preferred_tools"] = existing.get("preferred_tools", set()) | new_profile.get("preferred_tools", set())

    def _link_to_canonical(self, user_id: str, canonical_id: str):
        """Link a user ID to a canonical identity."""
        self._id_to_canonical[user_id] = canonical_id
        if canonical_id not in self._identity_graph:
            self._identity_graph[canonical_id] = {canonical_id}
        self._identity_graph[canonical_id].add(user_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get identity resolution statistics."""
        total_canonical = len(self._identity_graph)
        total_linked = sum(len(ids) for ids in self._identity_graph.values())
        multi_identity = sum(1 for ids in self._identity_graph.values() if len(ids) > 1)

        return {
            "canonical_identities": total_canonical,
            "total_linked_ids": total_linked,
            "multi_identity_users": multi_identity,
            "average_ids_per_user": round(total_linked / total_canonical, 2) if total_canonical > 0 else 0,
        }

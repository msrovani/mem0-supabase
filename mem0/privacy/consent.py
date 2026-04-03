"""
Privacy & Consent Architecture - Phase 2.3
Origin: Mem0 Trust Center (https://trust.mem0.ai/)
        GDPR compliance patterns, data governance for AI memory systems

This module provides:
- Per-item consent management
- Data retention lifecycle
- Deletion controls (right to be forgotten)
- Audit logging for all privacy operations
- Consent-based memory filtering
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ConsentType(str, Enum):
    """Types of consent for memory operations."""

    EXPLICIT = "explicit"  # User explicitly granted consent
    IMPLICIT = "implicit"  # Consent inferred from context
    REVOKED = "revoked"  # User revoked consent
    EXPIRED = "expired"  # Consent expired due to time


class MemoryType(str, Enum):
    """Types of memory that can have consent controls."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    PERSONAL = "personal"
    CONVERSATION = "conversation"
    BEHAVIORAL = "behavioral"
    ALL = "all"


class AuditAction(str, Enum):
    """Actions that are logged in the audit trail."""

    CONSENT_GRANTED = "consent_granted"
    CONSENT_REVOKED = "consent_revoked"
    MEMORY_DELETED = "memory_deleted"
    MEMORY_EXPORTED = "memory_exported"
    CONSENT_CHECKED = "consent_checked"
    RETENTION_ENFORCED = "retention_enforced"
    DATA_ACCESSED = "data_accessed"


class ConsentRecord:
    """Record of a consent grant/revocation."""

    def __init__(
        self,
        user_id: str,
        memory_type: MemoryType,
        consent_type: ConsentType = ConsentType.EXPLICIT,
        granted_at: Optional[str] = None,
        expires_at: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.id = str(uuid.uuid4())
        self.user_id = user_id
        self.memory_type = memory_type
        self.consent_type = consent_type
        self.granted_at = granted_at or datetime.now().isoformat()
        self.expires_at = expires_at
        self.metadata = metadata or {}
        self.is_active = self._check_active()

    def _check_active(self) -> bool:
        if self.consent_type == ConsentType.REVOKED:
            return False
        if self.expires_at:
            try:
                return datetime.now() < datetime.fromisoformat(self.expires_at)
            except ValueError:
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "memory_type": self.memory_type.value,
            "consent_type": self.consent_type.value,
            "granted_at": self.granted_at,
            "expires_at": self.expires_at,
            "is_active": self.is_active,
            "metadata": self.metadata,
        }


class AuditLogEntry:
    """An entry in the privacy audit log."""

    def __init__(
        self,
        action: AuditAction,
        user_id: str,
        details: Dict[str, Any],
        actor_id: Optional[str] = None,
    ):
        self.id = str(uuid.uuid4())
        self.timestamp = datetime.now().isoformat()
        self.action = action
        self.user_id = user_id
        self.actor_id = actor_id  # Who performed the action
        self.details = details

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "action": self.action.value,
            "user_id": self.user_id,
            "actor_id": self.actor_id,
            "details": self.details,
        }


class ConsentManager:
    """
    Manages consent for memory operations.

    Usage:
        manager = ConsentManager()
        manager.grant_consent("user-123", MemoryType.PERSONAL)
        if manager.check_consent("user-123", MemoryType.PERSONAL):
            # Safe to store/access personal memory
    """

    def __init__(self):
        self._consents: Dict[str, Dict[str, ConsentRecord]] = {}  # user_id -> {memory_type -> record}
        self._audit_log: List[AuditLogEntry] = []

    def grant_consent(
        self,
        user_id: str,
        memory_type: MemoryType,
        consent_type: ConsentType = ConsentType.EXPLICIT,
        expires_at: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConsentRecord:
        """Grant consent for a memory type."""
        if memory_type == MemoryType.ALL:
            # Grant for all types
            records = []
            for mt in MemoryType:
                if mt != MemoryType.ALL:
                    records.append(self.grant_consent(user_id, mt, consent_type, expires_at, metadata))
            return records[-1] if records else None

        record = ConsentRecord(user_id, memory_type, consent_type, expires_at=expires_at, metadata=metadata)

        if user_id not in self._consents:
            self._consents[user_id] = {}
        self._consents[user_id][memory_type.value] = record

        self._log_audit(
            AuditAction.CONSENT_GRANTED, user_id, {"record_id": record.id, "memory_type": memory_type.value}
        )
        logger.info(f"Consent granted: {user_id} for {memory_type.value}")
        return record

    def revoke_consent(self, user_id: str, memory_type: MemoryType) -> bool:
        """Revoke consent for a memory type."""
        if user_id not in self._consents:
            return False

        if memory_type.value not in self._consents[user_id]:
            return False

        self._consents[user_id][memory_type.value].consent_type = ConsentType.REVOKED
        self._consents[user_id][memory_type.value].is_active = False

        self._log_audit(AuditAction.CONSENT_REVOKED, user_id, {"memory_type": memory_type.value})
        logger.info(f"Consent revoked: {user_id} for {memory_type.value}")
        return True

    def check_consent(self, user_id: str, memory_type: MemoryType) -> bool:
        """Check if consent is active for a memory type."""
        if user_id not in self._consents:
            return False

        record = self._consents[user_id].get(memory_type.value)
        if record is None:
            return False

        # Refresh active status
        record.is_active = record._check_active()
        if not record.is_active and record.consent_type != ConsentType.REVOKED:
            record.consent_type = ConsentType.EXPIRED

        self._log_audit(
            AuditAction.CONSENT_CHECKED,
            user_id,
            {
                "memory_type": memory_type.value,
                "is_active": record.is_active,
            },
        )
        return record.is_active

    def get_all_consents(self, user_id: str) -> List[ConsentRecord]:
        """Get all consent records for a user."""
        if user_id not in self._consents:
            return []
        return list(self._consents[user_id].values())

    def delete_user_data(self, user_id: str) -> int:
        """Delete all consent records for a user (right to be forgotten)."""
        if user_id not in self._consents:
            return 0

        count = len(self._consents[user_id])
        del self._consents[user_id]

        self._log_audit(AuditAction.MEMORY_DELETED, user_id, {"records_deleted": count})
        logger.info(f"All consent data deleted for user: {user_id}")
        return count

    def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """Export all consent data for a user (GDPR data portability)."""
        consents = self.get_all_consents(user_id)
        user_audit = [entry.to_dict() for entry in self._audit_log if entry.user_id == user_id]

        self._log_audit(AuditAction.MEMORY_EXPORTED, user_id, {"records_exported": len(consents)})

        return {
            "user_id": user_id,
            "consents": [c.to_dict() for c in consents],
            "audit_log": user_audit,
            "exported_at": datetime.now().isoformat(),
        }

    def get_audit_log(
        self,
        user_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        limit: int = 100,
    ) -> List[AuditLogEntry]:
        """Get audit log entries with optional filters."""
        entries = self._audit_log
        if user_id:
            entries = [e for e in entries if e.user_id == user_id]
        if action:
            entries = [e for e in entries if e.action == action]
        return entries[-limit:]

    def _log_audit(self, action: AuditAction, user_id: str, details: Dict[str, Any]):
        """Add an entry to the audit log."""
        entry = AuditLogEntry(action, user_id, details)
        self._audit_log.append(entry)
        # Keep audit log manageable (last 10000 entries)
        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-10000:]

    def enforce_retention(
        self,
        user_id: str,
        memories: List[Dict[str, Any]],
        retention_days: int = 365,
    ) -> List[Dict[str, Any]]:
        """
        Filter memories based on retention policy and consent.
        Returns only memories that are allowed to be retained.
        """
        cutoff = datetime.now()
        allowed = []

        for memory in memories:
            # Check consent
            memory_type = MemoryType(memory.get("type", "semantic"))
            if not self.check_consent(user_id, memory_type):
                continue

            # Check retention period
            created_at = memory.get("created_at")
            if created_at:
                try:
                    created = datetime.fromisoformat(created_at)
                    age_days = (cutoff - created).days
                    if age_days > retention_days:
                        self._log_audit(
                            AuditAction.RETENTION_ENFORCED,
                            user_id,
                            {
                                "memory_id": memory.get("id"),
                                "age_days": age_days,
                            },
                        )
                        continue
                except ValueError:
                    pass

            allowed.append(memory)

        return allowed

"""
Procedural Memory System - Phase 2.1
Origin: AtomMem (https://github.com/RUCBM/AtomMem) - atomic CRUD memory operations
        Procedural memory in AI agents (how-to knowledge vs factual knowledge)

This module captures and stores procedural knowledge: workflows, tool patterns,
step-by-step processes, and "how-to" information that agents learn over time.

6-Category Memory Classification (from AtomMem):
1. EPISODIC - Specific events and experiences
2. SEMANTIC - Facts and general knowledge
3. PROCEDURAL - How-to knowledge, workflows, skills
4. WORKING - Current context and active tasks
5. META - Knowledge about knowledge (self-awareness)
6. TOOL - Tool usage patterns and configurations
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class MemoryCategory(str, Enum):
    """6-category memory classification from AtomMem."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    WORKING = "working"
    META = "meta"
    TOOL = "tool"


class ProcedureStep:
    """A single step in a procedural memory."""

    def __init__(
        self,
        step_number: int,
        action: str,
        description: str,
        tool_used: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        outcome: Optional[str] = None,
        success: bool = True,
    ):
        self.step_number = step_number
        self.action = action
        self.description = description
        self.tool_used = tool_used
        self.parameters = parameters or {}
        self.outcome = outcome
        self.success = success

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "action": self.action,
            "description": self.description,
            "tool_used": self.tool_used,
            "parameters": self.parameters,
            "outcome": self.outcome,
            "success": self.success,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcedureStep":
        return cls(
            step_number=data["step_number"],
            action=data["action"],
            description=data["description"],
            tool_used=data.get("tool_used"),
            parameters=data.get("parameters", {}),
            outcome=data.get("outcome"),
            success=data.get("success", True),
        )


class Procedure:
    """A complete procedural memory (workflow/skill)."""

    def __init__(
        self,
        name: str,
        category: MemoryCategory = MemoryCategory.PROCEDURAL,
        description: str = "",
        steps: Optional[List[ProcedureStep]] = None,
        tags: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        success_rate: float = 1.0,
        usage_count: int = 0,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ):
        self.id = str(uuid.uuid4())
        self.name = name
        self.category = category
        self.description = description
        self.steps = steps or []
        self.tags = tags or []
        self.user_id = user_id
        self.agent_id = agent_id
        self.context = context or {}
        self.success_rate = success_rate
        self.usage_count = usage_count
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or datetime.now().isoformat()

    def add_step(self, step: ProcedureStep):
        self.steps.append(step)
        self.steps.sort(key=lambda s: s.step_number)
        self.updated_at = datetime.now().isoformat()

    def record_outcome(self, success: bool):
        """Update success rate based on usage outcome."""
        self.usage_count += 1
        if success:
            self.success_rate = (self.success_rate * (self.usage_count - 1) + 1.0) / self.usage_count
        else:
            self.success_rate = (self.success_rate * (self.usage_count - 1)) / self.usage_count
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "tags": self.tags,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "context": self.context,
            "success_rate": self.success_rate,
            "usage_count": self.usage_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Procedure":
        steps = [ProcedureStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            name=data["name"],
            category=MemoryCategory(data.get("category", "procedural")),
            description=data.get("description", ""),
            steps=steps,
            tags=data.get("tags", []),
            user_id=data.get("user_id"),
            agent_id=data.get("agent_id"),
            context=data.get("context", {}),
            success_rate=data.get("success_rate", 1.0),
            usage_count=data.get("usage_count", 0),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


class ProceduralMemoryStore:
    """
    In-memory store for procedural memories.
    Can be extended with Supabase/SQLite persistence.
    """

    def __init__(self):
        self._procedures: Dict[str, Procedure] = {}
        self._index_by_name: Dict[str, List[str]] = {}
        self._index_by_tag: Dict[str, List[str]] = {}
        self._index_by_category: Dict[str, List[str]] = {}

    def store_procedure(self, procedure: Procedure) -> str:
        """Store a new procedure."""
        self._procedures[procedure.id] = procedure

        # Index by name
        name_key = procedure.name.lower()
        if name_key not in self._index_by_name:
            self._index_by_name[name_key] = []
        self._index_by_name[name_key].append(procedure.id)

        # Index by tags
        for tag in procedure.tags:
            if tag not in self._index_by_tag:
                self._index_by_tag[tag] = []
            self._index_by_tag[tag].append(procedure.id)

        # Index by category
        cat_key = procedure.category.value
        if cat_key not in self._index_by_category:
            self._index_by_category[cat_key] = []
        self._index_by_category[cat_key].append(procedure.id)

        logger.info(f"Stored procedure: {procedure.name} ({procedure.id})")
        return procedure.id

    def retrieve_procedure(self, name: str) -> Optional[Procedure]:
        """Retrieve a procedure by name."""
        name_key = name.lower()
        ids = self._index_by_name.get(name_key, [])
        if ids:
            return self._procedures.get(ids[0])
        return None

    def retrieve_by_id(self, procedure_id: str) -> Optional[Procedure]:
        """Retrieve a procedure by ID."""
        return self._procedures.get(procedure_id)

    def list_procedures(
        self,
        category: Optional[MemoryCategory] = None,
        tag: Optional[str] = None,
        user_id: Optional[str] = None,
        min_success_rate: float = 0.0,
    ) -> List[Procedure]:
        """List procedures with optional filters."""
        if category:
            ids = self._index_by_category.get(category.value, [])
        elif tag:
            ids = self._index_by_tag.get(tag, [])
        else:
            ids = list(self._procedures.keys())

        results = []
        for pid in ids:
            proc = self._procedures.get(pid)
            if proc is None:
                continue
            if user_id and proc.user_id != user_id:
                continue
            if proc.success_rate < min_success_rate:
                continue
            results.append(proc)

        return sorted(results, key=lambda p: p.success_rate, reverse=True)

    def search_procedures(self, query: str) -> List[Procedure]:
        """Search procedures by name/description keyword."""
        query_lower = query.lower()
        results = []
        for proc in self._procedures.values():
            if query_lower in proc.name.lower() or query_lower in proc.description.lower():
                results.append(proc)
            for step in proc.steps:
                if query_lower in step.action.lower() or query_lower in step.description.lower():
                    results.append(proc)
                    break
        return sorted(results, key=lambda p: p.usage_count, reverse=True)

    def delete_procedure(self, procedure_id: str) -> bool:
        """Delete a procedure (atomic CRUD - Delete)."""
        if procedure_id not in self._procedures:
            return False

        proc = self._procedures.pop(procedure_id)

        # Remove from indexes
        name_key = proc.name.lower()
        if name_key in self._index_by_name:
            self._index_by_name[name_key] = [pid for pid in self._index_by_name[name_key] if pid != procedure_id]
        for tag in proc.tags:
            if tag in self._index_by_tag:
                self._index_by_tag[tag] = [pid for pid in self._index_by_tag[tag] if pid != procedure_id]
        cat_key = proc.category.value
        if cat_key in self._index_by_category:
            self._index_by_category[cat_key] = [pid for pid in self._index_by_category[cat_key] if pid != procedure_id]

        logger.info(f"Deleted procedure: {proc.name} ({procedure_id})")
        return True

    def update_procedure(self, procedure_id: str, **kwargs) -> Optional[Procedure]:
        """Update a procedure (atomic CRUD - Update)."""
        proc = self._procedures.get(procedure_id)
        if proc is None:
            return None

        for key, value in kwargs.items():
            if hasattr(proc, key):
                setattr(proc, key, value)
        proc.updated_at = datetime.now().isoformat()

        logger.info(f"Updated procedure: {proc.name} ({procedure_id})")
        return proc

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about stored procedures."""
        by_category = {}
        for cat in MemoryCategory:
            by_category[cat.value] = len(self._index_by_category.get(cat.value, []))

        total_usage = sum(p.usage_count for p in self._procedures.values())
        avg_success = (
            sum(p.success_rate for p in self._procedures.values()) / len(self._procedures) if self._procedures else 0.0
        )

        return {
            "total_procedures": len(self._procedures),
            "by_category": by_category,
            "total_usage": total_usage,
            "average_success_rate": round(avg_success, 4),
        }

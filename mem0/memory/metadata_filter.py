"""
Multi-Scope Memory Metadata Filtering - Phase 2.2
Origin: Metadata filtering patterns in vector databases,
        multi-scope memory systems (user_id, agent_id, session_id, org_id)

This module provides advanced metadata filtering for memory queries,
supporting boolean combinations (AND/OR/NOT) and range queries.

Supported filter types:
- Exact match: {"actor_id": "user-123"}
- In list: {"actor_type": {"$in": ["user", "agent"]}}
- Range: {"created_at": {"$gte": "2024-01-01", "$lte": "2024-12-31"}}
- Exists: {"conversation_id": {"$exists": True}}
- Regex: {"memory": {"$regex": "python.*programming"}}
- Boolean combinations: {"$and": [...], "$or": [...], "$not": {...}}
"""

import logging
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class MemoryFilter:
    """
    Build and apply metadata filters to memory collections.

    Usage:
        # Simple exact match
        f = MemoryFilter({"actor_id": "user-123"})

        # Complex boolean combination
        f = MemoryFilter({
            "$and": [
                {"actor_type": {"$in": ["user", "agent"]}},
                {"created_at": {"$gte": "2024-01-01"}},
                {"$or": [
                    {"tags": {"$contains": "important"}},
                    {"confidence": {"$gte": 0.8}},
                ]},
            ]
        })

        # Apply to memories
        filtered = f.apply(memories)
    """

    def __init__(self, filter_expr: Dict[str, Any]):
        self.filter_expr = filter_expr
        self._compiled = self._compile(filter_expr)

    def apply(self, memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter a list of memories based on the filter expression."""
        return [m for m in memories if self._compiled(m)]

    def _compile(self, expr: Dict[str, Any]) -> Callable[[Dict[str, Any]], bool]:
        """Compile a filter expression into a predicate function."""
        if not expr:
            return lambda m: True

        # Handle boolean operators
        if "$and" in expr:
            predicates = [self._compile(sub) for sub in expr["$and"]]
            return lambda m: all(p(m) for p in predicates)

        if "$or" in expr:
            predicates = [self._compile(sub) for sub in expr["$or"]]
            return lambda m: any(p(m) for p in predicates)

        if "$not" in expr:
            inner = self._compile(expr["$not"])
            return lambda m: not inner(m)

        # Handle field-level conditions
        predicates = []
        for field, condition in expr.items():
            if field.startswith("$"):
                continue  # Skip boolean operators (handled above)
            predicates.append(self._compile_field(field, condition))

        # All field conditions are ANDed together
        return lambda m: all(p(m) for p in predicates)

    def _compile_field(self, field: str, condition: Any) -> Callable[[Dict[str, Any]], bool]:
        """Compile a single field condition into a predicate."""
        if not isinstance(condition, dict):
            # Simple equality
            return lambda m: self._get_nested(m, field) == condition

        predicates = []
        for op, value in condition.items():
            predicates.append(self._compile_operator(field, op, value))

        return lambda m: all(p(m) for p in predicates)

    def _compile_operator(self, field: str, op: str, value: Any) -> Callable[[Dict[str, Any]], bool]:
        """Compile a single operator into a predicate."""
        if op == "$eq":
            return lambda m: self._get_nested(m, field) == value
        elif op == "$ne":
            return lambda m: self._get_nested(m, field) != value
        elif op == "$in":
            return lambda m: self._get_nested(m, field) in value
        elif op == "$nin":
            return lambda m: self._get_nested(m, field) not in value
        elif op == "$gt":
            return lambda m: self._compare(m, field, value, lambda a, b: a > b)
        elif op == "$gte":
            return lambda m: self._compare(m, field, value, lambda a, b: a >= b)
        elif op == "$lt":
            return lambda m: self._compare(m, field, value, lambda a, b: a < b)
        elif op == "$lte":
            return lambda m: self._compare(m, field, value, lambda a, b: a <= b)
        elif op == "$exists":
            return lambda m: (self._get_nested(m, field) is not None) == value
        elif op == "$regex":
            pattern = re.compile(value, re.IGNORECASE)
            return lambda m: bool(pattern.search(str(self._get_nested(m, field) or "")))
        elif op == "$contains":
            return lambda m: value in (self._get_nested(m, field) or [])
        elif op == "$not_contains":
            return lambda m: value not in (self._get_nested(m, field) or [])
        elif op == "$is_null":
            return lambda m: self._get_nested(m, field) is None
        else:
            logger.warning(f"Unknown filter operator: {op}")
            return lambda m: True

    def _get_nested(self, obj: Dict[str, Any], path: str) -> Any:
        """Get a nested value from a dict using dot notation."""
        parts = path.split(".")
        current = obj
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def _compare(self, obj: Dict[str, Any], field: str, value: Any, cmp_fn: Callable) -> bool:
        """Compare values, handling type coercion for dates."""
        field_value = self._get_nested(obj, field)
        if field_value is None:
            return False

        # Try to coerce to comparable types
        try:
            # If both are strings that look like dates, compare as dates
            if isinstance(field_value, str) and isinstance(value, str):
                try:
                    fv = datetime.fromisoformat(field_value)
                    vv = datetime.fromisoformat(value)
                    return cmp_fn(fv, vv)
                except ValueError:
                    pass

            # Try numeric comparison
            return cmp_fn(float(field_value), float(value))
        except (ValueError, TypeError):
            # Fallback to string comparison
            return cmp_fn(str(field_value), str(value))


class FilterBuilder:
    """
    Fluent API for building memory filters.

    Usage:
        f = (FilterBuilder()
            .field("actor_id").eq("user-123")
            .and_field("confidence").gte(0.8)
            .or_field("tags").contains("important")
            .build())
    """

    def __init__(self):
        self._conditions: List[Dict[str, Any]] = []
        self._current_field: Optional[str] = None
        self._or_conditions: List[Dict[str, Any]] = []
        self._mode = "and"  # "and" or "or"

    def field(self, name: str) -> "FilterBuilder":
        """Start a condition on a field."""
        self._current_field = name
        return self

    def eq(self, value: Any) -> "FilterBuilder":
        self._add_condition(self._current_field, {"$eq": value})
        return self

    def ne(self, value: Any) -> "FilterBuilder":
        self._add_condition(self._current_field, {"$ne": value})
        return self

    def gt(self, value: Any) -> "FilterBuilder":
        self._add_condition(self._current_field, {"$gt": value})
        return self

    def gte(self, value: Any) -> "FilterBuilder":
        self._add_condition(self._current_field, {"$gte": value})
        return self

    def lt(self, value: Any) -> "FilterBuilder":
        self._add_condition(self._current_field, {"$lt": value})
        return self

    def lte(self, value: Any) -> "FilterBuilder":
        self._add_condition(self._current_field, {"$lte": value})
        return self

    def in_list(self, values: list) -> "FilterBuilder":
        self._add_condition(self._current_field, {"$in": values})
        return self

    def exists(self, value: bool = True) -> "FilterBuilder":
        self._add_condition(self._current_field, {"$exists": value})
        return self

    def regex(self, pattern: str) -> "FilterBuilder":
        self._add_condition(self._current_field, {"$regex": pattern})
        return self

    def contains(self, value: Any) -> "FilterBuilder":
        self._add_condition(self._current_field, {"$contains": value})
        return self

    def or_field(self, name: str) -> "FilterBuilder":
        """Switch to OR mode for the next condition."""
        self._mode = "or"
        self._current_field = name
        return self

    def and_field(self, name: str) -> "FilterBuilder":
        """Switch back to AND mode."""
        self._mode = "and"
        self._current_field = name
        return self

    def build(self) -> MemoryFilter:
        """Build the filter expression."""
        if not self._conditions and not self._or_conditions:
            return MemoryFilter({})

        if self._or_conditions and self._conditions:
            expr = {"$and": self._conditions + [{"$or": self._or_conditions}]}
        elif self._or_conditions:
            expr = {"$or": self._or_conditions}
        else:
            expr = {"$and": self._conditions} if len(self._conditions) > 1 else self._conditions[0]

        return MemoryFilter(expr)

    def _add_condition(self, field: str, condition: Dict[str, Any]):
        """Add a condition to the current mode."""
        full_condition = {field: condition}
        if self._mode == "or":
            self._or_conditions.append(full_condition)
            self._mode = "and"  # Reset to AND after OR
        else:
            self._conditions.append(full_condition)

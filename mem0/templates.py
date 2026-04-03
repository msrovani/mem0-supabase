"""
Memory Templates — Pre-defined schemas for consistent memory creation.

Provides validation, defaults, and type safety for memory entries.
Supports custom template registration and schema validation.

Usage:
    from mem0.templates import MemoryTemplate, TemplateRegistry

    registry = TemplateRegistry()
    registry.register(MemoryTemplate(
        name="fact",
        required_fields=["content", "user_id"],
        optional_fields=["confidence", "source"],
        defaults={"confidence": 0.5},
    ))

    validated = registry.validate("fact", {"content": "User likes pizza", "user_id": "u1"})
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = ["MemoryTemplate", "TemplateRegistry"]


@dataclass
class MemoryTemplate:
    """A template defining the schema for a type of memory."""

    name: str
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)
    defaults: Dict[str, Any] = field(default_factory=dict)
    validators: Dict[str, Callable[[Any], bool]] = field(default_factory=dict)
    description: str = ""


class TemplateRegistry:
    """
    Registry of memory templates with validation support.
    """

    def __init__(self):
        self._templates: Dict[str, MemoryTemplate] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register built-in memory templates."""
        self.register(
            MemoryTemplate(
                name="fact",
                required_fields=["content", "user_id"],
                optional_fields=["confidence", "source", "category"],
                defaults={"confidence": 0.5, "category": "general"},
                description="A factual statement about a user or entity.",
            )
        )

        self.register(
            MemoryTemplate(
                name="preference",
                required_fields=["content", "user_id"],
                optional_fields=["strength", "domain"],
                defaults={"strength": 0.5, "domain": "general"},
                description="A user preference or opinion.",
            )
        )

        self.register(
            MemoryTemplate(
                name="event",
                required_fields=["content", "user_id", "timestamp"],
                optional_fields=["location", "participants", "importance"],
                defaults={"importance": 0.5},
                description="A significant event or occurrence.",
            )
        )

        self.register(
            MemoryTemplate(
                name="relationship",
                required_fields=["content", "user_id", "related_to"],
                optional_fields=["relationship_type", "strength"],
                defaults={"relationship_type": "unknown", "strength": 0.5},
                description="A relationship between entities.",
            )
        )

    def register(self, template: MemoryTemplate) -> None:
        """Register a memory template."""
        self._templates[template.name] = template
        logger.debug(f"Registered memory template: {template.name}")

    def validate(self, template_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate data against a template and apply defaults.

        Args:
            template_name: Name of the template to validate against.
            data: The data to validate.

        Returns:
            Validated data with defaults applied.

        Raises:
            ValueError: If required fields are missing or validation fails.
        """
        template = self._templates.get(template_name)
        if not template:
            raise ValueError(f"Unknown template: {template_name}. Available: {list(self._templates.keys())}")

        # Check required fields
        missing = [f for f in template.required_fields if f not in data or data[f] is None]
        if missing:
            raise ValueError(f"Template '{template_name}' missing required fields: {missing}")

        # Apply defaults
        result = dict(data)
        for key, default_value in template.defaults.items():
            if key not in result:
                result[key] = default_value

        # Run custom validators
        for field_name, validator in template.validators.items():
            if field_name in result:
                if not validator(result[field_name]):
                    raise ValueError(f"Template '{template_name}': field '{field_name}' failed validation")

        result["_template"] = template_name
        return result

    def get_template(self, name: str) -> Optional[MemoryTemplate]:
        """Get a template by name."""
        return self._templates.get(name)

    def list_templates(self) -> List[str]:
        """List all registered template names."""
        return list(self._templates.keys())

    def get_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """Get template schema as a dict."""
        template = self._templates.get(name)
        if not template:
            return None
        return {
            "name": template.name,
            "description": template.description,
            "required": template.required_fields,
            "optional": template.optional_fields,
            "defaults": template.defaults,
        }

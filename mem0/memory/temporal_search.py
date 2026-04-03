"""
Temporal Search with NLP Parsing - Upstream Feature Integration
Origin: Mem0 v1.0.x (Feb 28, 2026) - Temporal Search Filtering
        "Memory search now understands time-based queries like
        'what happened last week' out of the box"

This module parses natural language temporal expressions and converts
them into structured date range filters for memory search.

Supported expressions:
- "last week", "this week", "next week"
- "last month", "this month", "next month"
- "yesterday", "today", "tomorrow"
- "X days/weeks/months/years ago"
- "in the last X days/hours"
- "since [date]", "before [date]", "after [date]"
- "between [date] and [date]"
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class TemporalParser:
    """
    Parses natural language temporal expressions into date range filters.

    Usage:
        parser = TemporalParser()
        result = parser.parse("what happened last week")
        # Returns: {"start": datetime(...), "end": datetime(...), "query": "what happened"}
    """

    def __init__(self):
        self._patterns = self._build_patterns()

    def _build_patterns(self) -> list:
        """Build regex patterns for temporal expressions."""
        return [
            # "in the last X days/hours/weeks/months/years"
            (
                r"(?:in\s+)?(?:the\s+)?last\s+(\d+)\s+(day|hour|week|month|year)s?",
                self._relative_past,
            ),
            # "X days/weeks/months/years ago"
            (
                r"(\d+)\s+(day|hour|week|month|year)s?\s+ago",
                self._ago,
            ),
            # "since yesterday/today/tomorrow"
            (
                r"since\s+(yesterday|today|tomorrow)",
                self._since_relative,
            ),
            # "before yesterday/today/tomorrow"
            (
                r"before\s+(yesterday|today|tomorrow)",
                self._before_relative,
            ),
            # "after yesterday/today/tomorrow"
            (
                r"after\s+(yesterday|today|tomorrow)",
                self._after_relative,
            ),
            # "last week/month/year"
            (
                r"last\s+(week|month|year)",
                self._last_period,
            ),
            # "this week/month/year"
            (
                r"this\s+(week|month|year)",
                self._this_period,
            ),
            # "next week/month/year"
            (
                r"next\s+(week|month|year)",
                self._next_period,
            ),
            # "yesterday", "today", "tomorrow"
            (
                r"\b(yesterday|today|tomorrow)\b",
                self._day_relative,
            ),
            # "since YYYY-MM-DD"
            (
                r"since\s+(\d{4}-\d{2}-\d{2})",
                self._since_date,
            ),
            # "before YYYY-MM-DD"
            (
                r"before\s+(\d{4}-\d{2}-\d{2})",
                self._before_date,
            ),
            # "after YYYY-MM-DD"
            (
                r"after\s+(\d{4}-\d{2}-\d{2})",
                self._after_date,
            ),
            # "between YYYY-MM-DD and YYYY-MM-DD"
            (
                r"between\s+(\d{4}-\d{2}-\d{2})\s+and\s+(\d{4}-\d{2}-\d{2})",
                self._between_dates,
            ),
        ]

    def parse(self, query: str, reference_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Parse a query for temporal expressions.

        Args:
            query: The search query (may contain temporal expressions)
            reference_time: The reference time for relative calculations (default: now)

        Returns:
            Dict with:
                - start: Start datetime (or None)
                - end: End datetime (or None)
                - cleaned_query: Query with temporal expressions removed
                - has_temporal: Whether a temporal expression was found
        """
        now = reference_time or datetime.now()
        cleaned_query = query.strip()
        start = None
        end = None
        has_temporal = False

        for pattern, handler in self._patterns:
            match = re.search(pattern, cleaned_query, re.IGNORECASE)
            if match:
                try:
                    start, end = handler(match, now)
                    has_temporal = True
                    # Remove the temporal expression from query
                    cleaned_query = cleaned_query[: match.start()] + cleaned_query[match.end() :]
                    cleaned_query = re.sub(r"\s+", " ", cleaned_query).strip()
                    break  # Only handle one temporal expression
                except Exception as e:
                    logger.warning(f"Temporal parsing error: {e}")

        return {
            "start": start,
            "end": end,
            "cleaned_query": cleaned_query,
            "has_temporal": has_temporal,
        }

    # --- Handler Methods ---

    def _relative_past(self, match, now):
        """Handle 'in the last X days/hours/weeks/months/years'"""
        amount = int(match.group(1))
        unit = match.group(2)
        delta = self._to_timedelta(amount, unit)
        start = now - delta
        return start, now

    def _ago(self, match, now):
        """Handle 'X days/weeks/months/years ago'"""
        amount = int(match.group(1))
        unit = match.group(2)
        delta = self._to_timedelta(amount, unit)
        target = now - delta
        # Return a 24-hour window around the target
        return target - timedelta(hours=12), target + timedelta(hours=12)

    def _since_relative(self, match, now):
        """Handle 'since yesterday/today/tomorrow'"""
        ref = self._resolve_day(match.group(1), now)
        return ref, now

    def _before_relative(self, match, now):
        """Handle 'before yesterday/today/tomorrow'"""
        ref = self._resolve_day(match.group(1), now)
        return None, ref

    def _after_relative(self, match, now):
        """Handle 'after yesterday/today/tomorrow'"""
        ref = self._resolve_day(match.group(1), now)
        return ref, None

    def _last_period(self, match, now):
        """Handle 'last week/month/year'"""
        period = match.group(1)
        if period == "week":
            # Last week: Monday to Sunday of previous week
            start_of_this_week = now - timedelta(days=now.weekday())
            start = start_of_this_week - timedelta(weeks=1)
            end = start_of_this_week
        elif period == "month":
            # Last month: first to last day of previous month
            first_of_this_month = now.replace(day=1)
            end = first_of_this_month
            start = (end - timedelta(days=1)).replace(day=1)
        elif period == "year":
            start = now.replace(year=now.year - 1, month=1, day=1)
            end = now.replace(month=1, day=1)
        return start, end

    def _this_period(self, match, now):
        """Handle 'this week/month/year'"""
        period = match.group(1)
        if period == "week":
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now
        elif period == "month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now
        elif period == "year":
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now
        return start, end

    def _next_period(self, match, now):
        """Handle 'next week/month/year'"""
        period = match.group(1)
        if period == "week":
            start_of_this_week = now - timedelta(days=now.weekday())
            start = start_of_this_week + timedelta(weeks=1)
            end = start + timedelta(weeks=1)
        elif period == "month":
            first_of_this_month = now.replace(day=1)
            start = first_of_this_month + timedelta(days=32)
            start = start.replace(day=1)
            end = (start + timedelta(days=32)).replace(day=1)
        elif period == "year":
            start = now.replace(year=now.year + 1, month=1, day=1)
            end = now.replace(year=now.year + 2, month=1, day=1)
        return start, end

    def _day_relative(self, match, now):
        """Handle 'yesterday/today/tomorrow'"""
        day = self._resolve_day(match.group(1), now)
        return day, day + timedelta(days=1)

    def _since_date(self, match, now):
        """Handle 'since YYYY-MM-DD'"""
        date = datetime.strptime(match.group(1), "%Y-%m-%d")
        return date, now

    def _before_date(self, match, now):
        """Handle 'before YYYY-MM-DD'"""
        date = datetime.strptime(match.group(1), "%Y-%m-%d")
        return None, date

    def _after_date(self, match, now):
        """Handle 'after YYYY-MM-DD'"""
        date = datetime.strptime(match.group(1), "%Y-%m-%d")
        return date, None

    def _between_dates(self, match, now):
        """Handle 'between YYYY-MM-DD and YYYY-MM-DD'"""
        start = datetime.strptime(match.group(1), "%Y-%m-%d")
        end = datetime.strptime(match.group(2), "%Y-%m-%d")
        return start, end

    # --- Utility Methods ---

    def _to_timedelta(self, amount: int, unit: str) -> timedelta:
        """Convert amount and unit to timedelta."""
        if unit == "hour":
            return timedelta(hours=amount)
        elif unit == "day":
            return timedelta(days=amount)
        elif unit == "week":
            return timedelta(weeks=amount)
        elif unit == "month":
            return timedelta(days=amount * 30)  # Approximate
        elif unit == "year":
            return timedelta(days=amount * 365)  # Approximate
        return timedelta(days=amount)

    def _resolve_day(self, day_name: str, now: datetime) -> datetime:
        """Resolve 'yesterday', 'today', 'tomorrow' to a datetime."""
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if day_name.lower() == "yesterday":
            return today - timedelta(days=1)
        elif day_name.lower() == "today":
            return today
        elif day_name.lower() == "tomorrow":
            return today + timedelta(days=1)
        return today

    def build_supabase_filter(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert parsed temporal result into a Supabase-compatible filter.

        Args:
            parsed: Result from parse()

        Returns:
            Dict with 'created_at' filter for Supabase queries
        """
        if not parsed["has_temporal"]:
            return {}

        filter_dict = {}
        if parsed["start"]:
            filter_dict["created_at_gte"] = parsed["start"].isoformat()
        if parsed["end"]:
            filter_dict["created_at_lte"] = parsed["end"].isoformat()

        return filter_dict


class TemporalSearchMixin:
    """
    Mixin that adds temporal search capability to memory classes.

    Usage:
        class MemoryWithTemporal(TemporalSearchMixin, Memory):
            pass

        memory = MemoryWithTemporal()
        results = memory.temporal_search("what did I discuss last week", user_id="user-1")
    """

    def temporal_search(self, query: str, **search_kwargs) -> Dict[str, Any]:
        """
        Search memories with natural language temporal expressions.

        Args:
            query: Search query (may contain temporal expressions like "last week")
            **search_kwargs: Additional arguments passed to the base search method

        Returns:
            Search results with temporal filtering applied
        """
        parser = TemporalParser()
        parsed = parser.parse(query)

        # Use cleaned query for semantic search
        search_query = parsed["cleaned_query"] if parsed["has_temporal"] else query

        # Build temporal filters
        temporal_filters = parser.build_supabase_filter(parsed)

        # Merge with existing filters
        existing_filters = search_kwargs.get("filters", {})
        merged_filters = {**existing_filters, **temporal_filters}
        search_kwargs["filters"] = merged_filters

        # Call the base search method
        if hasattr(self, "search"):
            results = self.search(search_query, **search_kwargs)
        else:
            raise NotImplementedError("Base class must implement 'search' method")

        # Add temporal metadata to results
        if isinstance(results, dict) and parsed["has_temporal"]:
            results["temporal_context"] = {
                "start": parsed["start"].isoformat() if parsed["start"] else None,
                "end": parsed["end"].isoformat() if parsed["end"] else None,
                "original_query": query,
                "cleaned_query": search_query,
            }

        return results

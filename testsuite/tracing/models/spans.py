"""Span-related data models for distributed tracing"""

import json
from dataclasses import dataclass
from typing import Any

from .logs import LogEntry


@dataclass(frozen=True)
class SpanReference:
    """Represents a reference to another span"""

    ref_type: str  # "CHILD_OF", "FOLLOWS_FROM"
    trace_id: str
    span_id: str

    @classmethod
    def from_dict(cls, data: dict) -> "SpanReference":
        """Create SpanReference from Jaeger API response dict"""
        return cls(
            ref_type=data.get("refType", ""),
            trace_id=data.get("traceID", ""),
            span_id=data.get("spanID", ""),
        )


@dataclass(frozen=True)
class Span:  # pylint: disable=too-many-instance-attributes
    """Represents a single span in a distributed trace"""

    operation_name: str
    span_id: str
    trace_id: str
    start_time: int
    duration: int  # Duration in microseconds (must be non-negative)
    tags: dict[str, Any]
    logs: list[LogEntry]
    references: list[SpanReference]
    process_id: str

    @classmethod
    def from_dict(cls, data: dict):
        """Create Span from Jaeger API response dict"""
        # Convert tags list to dict, parsing JSON strings into Python objects
        # Note: If duplicate keys exist, we keep the first occurrence
        tags_dict = {}
        for tag in data.get("tags", []):
            key = tag.get("key", "").strip()
            if not key:  # Skip malformed tags without keys or whitespace-only keys
                continue

            # Skip duplicate keys - keep first occurrence
            if key in tags_dict:
                continue

            value = tag.get("value", "")

            # Try to parse JSON strings (arrays/objects) into Python objects
            if isinstance(value, str):
                stripped = value.strip()
                if stripped.startswith("[") or stripped.startswith("{"):
                    try:
                        value = json.loads(stripped)
                    except json.JSONDecodeError:
                        pass  # Keep as string if not valid JSON

            tags_dict[key] = value

        # Convert logs list to LogEntry objects
        logs = [LogEntry.from_dict(log_data) for log_data in data.get("logs", [])]

        # Convert references list to SpanReference objects
        references = [SpanReference.from_dict(ref_data) for ref_data in data.get("references", [])]

        duration = data.get("duration", 0)
        # Negative durations don't make sense, but we don't fail on them
        # to be defensive against potentially malformed trace data
        duration = max(duration, 0)

        return cls(
            operation_name=data.get("operationName", ""),
            span_id=data.get("spanID", ""),
            trace_id=data.get("traceID", ""),
            start_time=data.get("startTime", 0),
            duration=duration,
            tags=tags_dict,
            logs=logs,
            references=references,
            process_id=data.get("processID", ""),
        )

    def get_tag(self, key: str, default=None) -> Any:
        """Get tag value by key"""
        return self.tags.get(key, default)

    def has_tag(self, key: str, value: Any = None) -> bool:  # pylint: disable=too-many-return-statements
        """
        Check if span has a tag with matching value.

        Args:
            key: Tag key to check
            value: Optional value to match. Matching rules:
                - If tag value is a list: checks exact membership
                - If both are strings: checks substring match (case-insensitive)
                - If types differ but one is numeric: try type coercion
                - Otherwise: checks equality

        Returns:
            True if tag exists (and matches value if provided)
        """
        if key not in self.tags:
            return False
        if value is None:
            return True

        tag_value = self.tags[key]

        # If tag value is a list, check exact membership
        if isinstance(tag_value, list):
            return value in tag_value

        # If both are strings, do case-insensitive substring match for backward compatibility
        if isinstance(value, str) and isinstance(tag_value, str):
            return str(value).lower() in str(tag_value).lower()

        # Try direct equality first
        if value == tag_value:
            return True

        # Handle type coercion for numeric comparisons (e.g., "429" vs 429)
        # This handles cases where tags are stored as strings but compared as ints
        if isinstance(value, (int, float)) and isinstance(tag_value, str):
            try:
                return value == type(value)(tag_value)
            except (ValueError, TypeError):
                return False
        if isinstance(tag_value, (int, float)) and isinstance(value, str):
            try:
                return type(tag_value)(value) == tag_value
            except (ValueError, TypeError):
                return False

        return False

    def get_parent_id(self) -> str | None:
        """Get parent span ID from CHILD_OF reference"""
        for ref in self.references:
            if ref.ref_type == "CHILD_OF":
                return ref.span_id
        return None

    def has_log_field(self, key: str, value: str | None = None) -> bool:
        """Check if any log entry has a field with exact value match"""
        for log_entry in self.logs:
            if log_entry.has_field(key, value):
                return True
        return False

"""Tracing data models for Jaeger/Tempo traces and spans."""

import json
from dataclasses import dataclass
from typing import Optional, Callable


@dataclass
class Span:
    """Represents a single span in a distributed trace."""

    operation_name: str
    span_id: str
    trace_id: str
    start_time: int
    duration: int
    tags: dict[str, str | int | bool]
    logs: list[dict]
    references: list[dict]
    process_id: str

    @classmethod
    def from_dict(cls, data: dict) -> "Span":
        """Create Span from Jaeger API response dict."""
        # Convert tags list to dict, parsing JSON strings into Python objects
        tags_dict = {}
        for tag in data.get("tags", []):
            key = tag["key"]
            value = tag["value"]

            # Try to parse JSON strings (arrays/objects) into Python objects
            if isinstance(value, str) and (value.startswith('[') or value.startswith('{')):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass  # Keep as string if not valid JSON

            tags_dict[key] = value

        return cls(
            operation_name=data.get("operationName", ""),
            span_id=data.get("spanID", ""),
            trace_id=data.get("traceID", ""),
            start_time=data.get("startTime", 0),
            duration=data.get("duration", 0),
            tags=tags_dict,
            logs=data.get("logs", []),
            references=data.get("references", []),
            process_id=data.get("processID", ""),
        )

    def get_tag(self, key: str, default=None):
        """Get tag value by key."""
        return self.tags.get(key, default)

    def has_tag(self, key: str, value: str | None = None) -> bool:
        """
        Check if span has a tag.

        Args:
            key: Tag key to check
            value: Optional value to match (list membership or substring match)

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

        # Otherwise substring match (for strings and other types)
        return str(value) in str(tag_value)

    def get_parent_id(self) -> Optional[str]:
        """Get parent span ID from CHILD_OF reference."""
        for ref in self.references:
            if ref.get("refType") == "CHILD_OF":
                return ref.get("spanID")
        return None


@dataclass
class Trace:
    """Represents a distributed trace with multiple spans."""

    trace_id: str
    spans: list[Span]
    processes: dict

    @classmethod
    def from_dict(cls, data: dict) -> "Trace":
        """Create Trace from Jaeger API response dict."""
        spans = [Span.from_dict(span_data) for span_data in data.get("spans", [])]
        return cls(
            trace_id=data.get("traceID", ""),
            spans=spans,
            processes=data.get("processes", {}),
        )

    def filter_spans(
        self,
        operation_name: str | None = None,
        tags: dict | None = None,
        predicate: Callable[[Span], bool] | None = None,
    ) -> list[Span]:
        """
        Filter spans by operation name, tag values, and/or custom predicate.

        Tag matching checks if the expected value is contained in the span's tag value.
        For list-type tags, checks exact membership.

        Args:
            operation_name: Filter by operation name (exact match)
            tags: Filter by tags (list membership or substring match)
            predicate: Custom filter function that takes a Span and returns bool

        Returns:
            List of matching spans
        """
        return [
            span
            for span in self.spans
            if (operation_name is None or span.operation_name == operation_name)
            and (tags is None or all(span.has_tag(k, str(v)) for k, v in tags.items()))
            and (predicate is None or predicate(span))
        ]

    def get_process_services(self) -> set[str]:
        """Get set of service names from all processes."""
        return {process.get("serviceName", "") for process in self.processes.values()}
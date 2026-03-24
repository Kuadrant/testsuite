"""Trace-related data models for distributed tracing."""

from dataclasses import dataclass
from typing import Any, Callable

from .spans import Span


@dataclass(frozen=True)
class Trace:
    """
    Represents a distributed trace with multiple spans.

    Note: Frozen to prevent accidental modification. Internal collections (spans,
    processes) should not be modified after creation.
    """

    trace_id: str
    spans: list[Span]
    processes: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict) -> "Trace":
        """Create Trace from Jaeger API response dict."""
        spans = [Span.from_dict(span_data) for span_data in data.get("spans", [])]
        return cls(
            trace_id=data.get("traceID", ""),
            spans=spans,
            processes=data.get("processes", {}),
        )

    def filter_spans(self, *predicates: Callable[[Span], bool]) -> list[Span]:
        """
        Filter spans using one or more predicates.

        All predicates must return True for a span to be included.
        Use Span properties and Python operators directly in your predicates.

        Args:
            *predicates: Filter functions that take a Span and return bool

        Returns:
            List of matching spans

        Examples:
            # Single condition
            trace.filter_spans(lambda s: s.operation_name == "controller.reconcile")

            # Multiple conditions (AND)
            trace.filter_spans(
                lambda s: s.operation_name.startswith("reconciler."),
                lambda s: s.duration > 50
            )

            # Complex single predicate
            trace.filter_spans(
                lambda s: s.duration > 50 and "wasm" in s.operation_name
            )

            # Use any Span property
            trace.filter_spans(
                lambda s: s.has_tag("policy.kind", "AuthPolicy"),
                lambda s: len(s.logs) > 0,
                lambda s: s.get_parent_id() is not None
            )
        """
        if not predicates:
            return list(self.spans)

        return [span for span in self.spans if all(pred(span) for pred in predicates)]

    def get_process_services(self) -> set[str]:
        """Get set of service names from all processes."""
        return {process.get("serviceName", "") for process in self.processes.values()}

    def get_root_spans(self) -> list[Span]:
        """Get spans with no parent (trace entry points)."""
        return [span for span in self.spans if span.get_parent_id() is None]

    def get_span_by_id(self, span_id: str) -> Span | None:
        """Look up a span by its span ID."""
        for span in self.spans:
            if span.span_id == span_id:
                return span
        return None

    def get_children(self, span_id: str) -> list[Span]:
        """Get all direct child spans of the given span."""
        return [span for span in self.spans if span.get_parent_id() == span_id]


    def validate_trace_consistency(self) -> list[str]:
        """
        Validate trace structure and return list of errors.

        Checks:
        - All spans have matching trace_id
        - Parent references point to existing spans
        - No circular references

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        for span in self.spans:
            # Check trace_id consistency
            if span.trace_id != self.trace_id:
                errors.append(
                    f"Span {span.span_id} has mismatched trace_id: "
                    f"expected {self.trace_id}, got {span.trace_id}"
                )

            # Check parent reference validity
            parent_id = span.get_parent_id()
            if parent_id:
                parent_span = self.get_span_by_id(parent_id)
                if not parent_span:
                    errors.append(
                        f"Span {span.span_id} references non-existent parent {parent_id}"
                    )

        return errors
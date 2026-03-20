"""Jaeger Tracing client"""

import json

import backoff
from apyproxy import ApyProxy
from httpx import Client

from testsuite.tracing import TracingClient
from testsuite.tracing.models import Trace, Span


class JaegerClient(TracingClient):
    """Tracing client for traces management"""

    def __init__(self, collector_url: str, query_url: str, client: Client):
        self._collector_url = collector_url
        self._query_url = query_url
        self.query = ApyProxy(self.query_url, session=client)

    @property
    def insecure(self):
        """So far, we only support insecure tracing as we depend on internal service which is insecure by default"""
        return True

    @property
    def collector_url(self):
        return self._collector_url

    @property
    def query_url(self):
        return self._query_url

    @backoff.on_predicate(backoff.fibo, lambda x: x == [], max_tries=7, jitter=None)
    def get_traces(self, service: str, tags: dict, min_processes: int = 0) -> list[Trace]:
        """Gets trace from tracing backend Tempo or Jaeger.
        If min_processes is set, retries until at least that many service processes are present.

        Returns:
            List of Trace objects
        """
        params = {"service": service, "tags": json.dumps(tags)}
        traces_data = self.query.api.traces.get(params=params).json()["data"]
        if not traces_data or (min_processes and len(traces_data[0]["processes"]) < min_processes):
            return []

        # Convert to Trace objects
        return [Trace.from_dict(trace_data) for trace_data in traces_data]

    # @staticmethod
    # def filter_spans(spans, operation_name=None, tags=None):
    #     """Filters spans by operation name and/or tag values.
    #     Tag matching checks if the expected value is contained in the span's tag value.
    #
    #     Works with both Span objects and raw dicts for backward compatibility.
    #     """
    #     result = spans
    #     if operation_name:
    #         result = [
    #             span for span in result
    #             if (span.operation_name if isinstance(span, Span) else span.get("operationName")) == operation_name
    #         ]
    #     if tags:
    #         for key, expected_value in tags.items():
    #             if result and isinstance(result[0], Span):
    #                 # Working with Span objects
    #                 result = [span for span in result if span.has_tag(key, str(expected_value))]
    #             else:
    #                 # Working with raw dicts (backward compatibility)
    #                 result = [
    #                     span
    #                     for span in result
    #                     if any(str(expected_value) in str(t["value"]) for t in span.get("tags", []) if t["key"] == key)
    #                 ]
    #     return result

    # @staticmethod
    # def get_tags_dict(span):
    #     """Converts span tags to dictionary for easier access.
    #     Works with both Span objects and raw dicts."""
    #     if isinstance(span, Span):
    #         return span.tags
    #     return {tag["key"]: tag["value"] for tag in span.get("tags", [])}
    #
    # @staticmethod
    # def get_parent_id(span):
    #     """Extracts parent span ID from the CHILD_OF reference.
    #     Works with both Span objects and raw dicts."""
    #     if isinstance(span, Span):
    #         return span.get_parent_id()
    #
    #     for ref in span.get("references", []):
    #         if ref["refType"] == "CHILD_OF":
    #             return ref["spanID"]
    #     return None
    #
    # def get_spans_by_operation(self, request_id, service, operation_name, tag_name="request_id"):
    #     """
    #     Get spans from a trace by request ID, filtered by service and operation name.
    #
    #     Args:
    #         request_id: The request ID to search for
    #         service: Service name to filter traces by
    #         operation_name: Operation name to filter spans by
    #         tag_name: Tag name containing the request ID (default: "request_id")
    #
    #     Returns:
    #         List of Span objects matching the criteria
    #     """
    #     # Get trace by request_id tag
    #     traces = self.get_trace(service=service, tags={tag_name: request_id})
    #     if not traces:
    #         return []
    #
    #     # Extract all spans from the trace(s) and filter by operation name
    #     matching_spans = []
    #     for trace in traces:
    #         matching_spans.extend(trace.filter_spans(operation_name=operation_name))
    #
    #     return matching_spans

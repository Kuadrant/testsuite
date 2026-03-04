"""Jaeger Tracing client"""

import json

import backoff
from apyproxy import ApyProxy
from httpx import Client

from testsuite.tracing import TracingClient


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
    def get_trace(self, service: str, tags: dict, min_processes: int = 0):
        """Gets trace from tracing backend Tempo or Jaeger.
        If min_processes is set, retries until at least that many service processes are present."""
        params = {"service": service, "tags": json.dumps(tags)}
        traces = self.query.api.traces.get(params=params).json()["data"]
        if not traces or (min_processes and len(traces[0]["processes"]) < min_processes):
            return []
        return traces

    @staticmethod
    def filter_spans(spans, operation_name=None, tags=None):
        """Filters spans by operation name and/or tag values.
        Tag matching checks if the expected value is contained in the span's tag value."""
        result = spans
        if operation_name:
            result = [span for span in result if span.get("operationName") == operation_name]
        if tags:
            for key, expected_value in tags.items():
                result = [
                    span
                    for span in result
                    if any(str(expected_value) in str(t["value"]) for t in span.get("tags", []) if t["key"] == key)
                ]
        return result

    @staticmethod
    def get_tags_dict(span):
        """Converts span tags list to dictionary for easier access."""
        return {tag["key"]: tag["value"] for tag in span.get("tags", [])}

    @staticmethod
    def get_parent_id(span):
        """Extracts parent span ID from the CHILD_OF reference. Returns None if no parent."""
        for ref in span.get("references", []):
            if ref["refType"] == "CHILD_OF":
                return ref["spanID"]
        return None

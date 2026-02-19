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
    def get_trace(self, service: str, tags: dict):
        """Gets trace from tracing backend Tempo or Jaeger."""
        params = {"service": service, "tags": json.dumps(tags)}
        return self.query.api.traces.get(params=params).json()["data"]

    def get_spans(self, service: str, tags: dict):
        """Gets spans from trace. Returns list of spans or empty list if trace not found."""
        trace = self.get_trace(service=service, tags=tags)
        if not trace:
            return []
        return trace[0].get("spans", [])

    def get_spans_by_operation(self, service: str, operation_name: str, tags: dict):
        """Gets spans filtered by operation name from trace."""
        spans = self.get_spans(service=service, tags=tags)
        return [span for span in spans if span.get("operationName") == operation_name]

    def get_full_trace(self, service: str, min_processes: int, tags: dict):
        """Gets trace, retrying until at least `min_processes` service processes are present."""

        @backoff.on_predicate(
            backoff.fibo,
            lambda x: len(x) == 0 or len(x[0]["processes"]) < min_processes,
            max_tries=5,
            jitter=None,
        )
        def _fetch():
            return self.get_trace(service=service, tags=tags)

        return _fetch()

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

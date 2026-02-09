"""Jaeger Tracing client"""

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
    def get_trace(self, request_id: str, service: str, tag_name: str, tags=None):
        """Gets trace from tracing backend Tempo or Jaeger."""
        if tags is None:
            tags = {}

        tags.update({"service": service, "tags": f'{{"{tag_name}":"{request_id}"}}'})
        return self.query.api.traces.get(params=tags).json()["data"]

    def get_spans(self, request_id: str, service: str, tag_name: str = "request_id", tags=None):
        """Gets spans from trace. Returns list of spans or empty list if trace not found."""
        trace = self.get_trace(request_id=request_id, service=service, tag_name=tag_name, tags=tags)
        if not trace:
            return []
        return trace[0].get("spans", [])

    def get_spans_by_operation(
        self, request_id: str, service: str, operation_name: str, tag_name: str = "request_id", tags=None
    ):
        """Gets spans filtered by operation name from trace."""
        spans = self.get_spans(request_id=request_id, service=service, tag_name=tag_name, tags=tags)
        return [span for span in spans if span.get("operationName") == operation_name]

    @staticmethod
    def get_tags_dict(span):
        """Converts span tags list to dictionary for easier access."""
        return {tag["key"]: tag["value"] for tag in span.get("tags", [])}

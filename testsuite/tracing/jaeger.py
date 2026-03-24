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

"""Jaeger Tracing client"""

import json
from typing import Optional

import backoff
from apyproxy import ApyProxy
from httpx import Client

from testsuite.tracing import TracingClient
from testsuite.tracing.models import Trace


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
    def get_traces(
        self,
        service: str,
        tags: Optional[dict[str, str]] = None,
        min_processes: int = 0,
        start_time: Optional[int] = None,
    ) -> list[Trace]:
        """Gets trace from tracing backend Tempo or Jaeger.
        If min_processes is set, retries until at least that many service processes are present.

        Args:
            service: Service name to filter traces
            tags: Optional tags to filter traces
            min_processes: Minimum number of processes required in traces
            start_time: Optional start time in microseconds (filters traces that started after this time)

        Returns:
            List of Trace objects
        """
        params = {"service": service}
        if tags:
            params["tags"] = json.dumps(tags)
        if start_time:
            params["start"] = str(start_time)

        traces_data = self.query.api.traces.get(params=params).json()["data"]
        if not traces_data:
            return []

        # Filter traces that meet min_processes requirement
        if min_processes:
            traces_data = [trace for trace in traces_data if len(trace.get("processes", {})) >= min_processes]
            if not traces_data:
                return []

        # Convert to Trace objects
        return [Trace.from_dict(trace_data) for trace_data in traces_data]

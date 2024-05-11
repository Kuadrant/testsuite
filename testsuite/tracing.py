"""Module with Tracing client for traces management"""

from typing import Optional

import backoff
from apyproxy import ApyProxy

from testsuite.httpx import KuadrantClient


class TracingClient:
    """Tracing client for traces management"""

    def __init__(self, collector_url: str, query_url: str, client: KuadrantClient = None):
        self.collector_url = collector_url
        self.client = client or KuadrantClient(verify=False)
        self.query = ApyProxy(query_url, session=self.client)

    @backoff.on_predicate(backoff.fibo, lambda x: x == [], max_tries=7, jitter=None)
    def _get_trace(
        self,
        request_id: str,
        service: str,
        tags=None,
    ):
        """Gets trace from tracing backend Tempo or Jaeger"""
        if tags is None:
            tags = {}

        if "jaeger" in self.collector_url:
            tags.update({"service": service, "tags": f'{{"authorino.request_id":"{request_id}"}}'})
            return self.query.api.traces.get(params=tags).json()["data"]

        tags.update({"service.name": service, "authorino.request_id": request_id})
        return self.query.api.search.get(params=tags).json()["traces"]

    def find_trace(self, request_id: str, service: str) -> Optional[dict]:
        """Find trace in tracing client by tags service name and `authorino.request_id`"""
        return self._get_trace(request_id, service)

    def find_tagged_trace(self, request_id: str, service: str, tag: dict) -> Optional[dict]:
        """Find trace in tracing client by tags service name, authorino request id and tag key-value pair"""
        return self._get_trace(request_id, service, tag)

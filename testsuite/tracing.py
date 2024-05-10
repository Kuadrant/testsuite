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
    def _find_trace(self, request_id: str, tags=None):
        if tags is None:
            tags = {}
        tags.update({"service.name": "authorino", "authorino.request_id": request_id})
        return self.query.api.search.get(params=tags).json()["traces"]

    def find_trace(self, request_id: str) -> Optional[dict]:
        """Find trace in tracing client by tag `authorino.request_id`"""
        return self._find_trace(request_id)

    def find_tagged_trace(self, request_id: str, tag: dict) -> Optional[dict]:
        """Find trace in tracing client by authorino request id and tag key-value pair"""
        return self._find_trace(request_id, tag)

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
    def search(self, request_id: str, service: str, tags=None):
        """Gets trace from tracing backend Tempo or Jaeger"""
        if tags is None:
            tags = {}

        tags.update({"service": service, "tags": f'{{"authorino.request_id":"{request_id}"}}'})
        return self.query.api.traces.get(params=tags).json()["data"]

"""Tempo tracing"""

import backoff

from testsuite.tracing.jaeger import JaegerClient


class RemoteTempoClient(JaegerClient):
    """Client to a Tempo that is deployed remotely"""

    @backoff.on_predicate(backoff.fibo, lambda x: x == [], max_tries=7, jitter=None)
    def search(self, request_id: str, service: str, tags=None):
        if tags is None:
            tags = {}

        tags.update({"service.name": service, "authorino.request_id": request_id})
        return self.query.api.search.get(params=tags).json()["traces"]

"""Tempo tracing"""

import backoff

from testsuite.tracing.jaeger import JaegerClient


class RemoteTempoClient(JaegerClient):
    """Client to a Tempo that is deployed remotely"""

    @backoff.on_predicate(backoff.fibo, lambda x: x == [], max_tries=7, jitter=None)
    def get_trace(self, request_id: str, service: str, tag_name: str, tags=None):
        """Gets trace from Tempo tracing backend."""
        if tags is None:
            tags = {}

        tags.update({"service.name": service, tag_name: request_id})
        return self.query.api.get_trace.get(params=tags).json()["traces"]

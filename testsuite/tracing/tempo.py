"""Tempo tracing"""

import backoff

from testsuite.tracing.jaeger import JaegerClient


class RemoteTempoClient(JaegerClient):
    """Client to a Tempo that is deployed remotely"""

    @backoff.on_predicate(backoff.fibo, lambda x: x == [], max_tries=7, jitter=None)
    def get_trace(self, service: str, tags: dict):
        """Gets trace from Tempo tracing backend."""
        params = {"service.name": service}
        params.update(tags)
        return self.query.api.get_trace.get(params=params).json()["traces"]

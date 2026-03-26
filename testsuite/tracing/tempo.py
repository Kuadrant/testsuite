"""Tempo tracing"""

import backoff

from testsuite.tracing.jaeger import JaegerClient


class RemoteTempoClient(JaegerClient):
    """Client to a Tempo that is deployed remotely"""

    @backoff.on_predicate(backoff.fibo, lambda x: x == [], max_tries=7, jitter=None)
    def get_traces(self, service: str, tags: dict = None, min_processes: int = 0):
        """Gets trace from Tempo tracing backend.
        If min_processes is set, retries until at least that many service processes are present"""
        params = {"service.name": service}
        if tags:
            params.update(tags)
        traces = self.query.api.get_traces.get(params=params).json()["traces"]
        if min_processes and traces and len(traces[0]["processes"]) < min_processes:
            return []
        return traces

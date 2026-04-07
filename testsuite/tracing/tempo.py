"""Tempo tracing"""

from typing import Optional

import backoff

from testsuite.tracing.jaeger import JaegerClient
from testsuite.tracing.models import Trace


class RemoteTempoClient(JaegerClient):
    """Client to a Tempo that is deployed remotely"""

    @backoff.on_predicate(backoff.fibo, lambda x: x == [], max_tries=7, jitter=None)
    def get_traces(
        self,
        service: str,
        tags: Optional[dict[str, str]] = None,
        min_processes: int = 0,
        lookback: Optional[str] = None,
        start_time: Optional[int] = None,
    ) -> list[Trace]:
        """Gets trace from Tempo tracing backend.
        If min_processes is set, retries until at least that many service processes are present"""
        params = {"service.name": service}
        if tags:
            params.update(tags)
        if lookback:
            params["lookback"] = lookback
        if start_time:
            params["start"] = start_time
        traces_data = self.query.api.get_traces.get(params=params).json()["traces"]
        if not traces_data:
            return []

        # Filter traces that meet min_processes requirement
        if min_processes:
            traces_data = [trace for trace in traces_data if len(trace.get("processes", {})) >= min_processes]
            if not traces_data:
                return []

        # Convert to Trace objects
        return [Trace.from_dict(trace_data) for trace_data in traces_data]

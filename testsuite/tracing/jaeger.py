"""Jaeger Tracing client"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import backoff
from apyproxy import ApyProxy
from httpx import Client, HTTPStatusError

from testsuite.tracing import TracingClient
from testsuite.tracing.models import Trace
from testsuite.utils.constants import TRACING_MAX_RETRIES


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

    @backoff.on_predicate(backoff.fibo, lambda x: x == [], max_tries=TRACING_MAX_RETRIES, jitter=None)
    def get_traces(
        self,
        service: str,
        attributes: Optional[dict[str, str]] = None,
        min_processes: int = 0,
        start_time: Optional[int] = None,
    ) -> list[Trace]:
        """Gets traces from Jaeger v3 API.
        If min_processes is set, retries until at least that many service processes are present.
        If start_time is set, only returns traces that started after that time (in microseconds).

        Returns:
            List of Trace objects
        """
        now = datetime.now(timezone.utc)
        if start_time is not None:
            start_dt = datetime.fromtimestamp(start_time / 1_000_000, tz=timezone.utc)
        else:
            start_dt = now - timedelta(hours=1)

        params = {
            "query.service_name": service,
            "query.start_time_min": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "query.start_time_max": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        try:
            response = self.query.api.v3.traces.get(params=params).json()
        except HTTPStatusError as exc:
            # Jaeger 404s on a service it has never seen. Span export is asynchronous, so a
            # service that has only just started reporting looks the same as an unknown one.
            # Treat it as "no traces yet" and let the retry above decide when to give up.
            if exc.response.status_code == 404:
                return []
            raise

        resource_spans = response.get("result", {}).get("resourceSpans", [])
        if not resource_spans:
            return []

        traces = Trace.from_otlp(resource_spans)

        if attributes:
            traces = [t for t in traces if self._trace_matches_attributes(t, attributes)]

        if min_processes:
            traces = [t for t in traces if len(t.processes) >= min_processes]

        return traces

    @staticmethod
    def _trace_matches_attributes(trace: Trace, attributes: dict[str, str]) -> bool:
        """Check if any span in the trace has all the requested attributes.
        Also checks resource-level attributes from the span's own process."""
        for span in trace.spans:
            process_attrs = trace.processes.get(span.process_id, {}).get("attributes", {})
            if all(
                span.has_attribute(key, value) or process_attrs.get(key) == value for key, value in attributes.items()
            ):
                return True
        return False

"""Module with Tracing client for traces management"""

from typing import Optional, Iterator

import backoff
from apyproxy import ApyProxy

from testsuite.httpx import KuadrantClient


class TracingClient:
    """Tracing client for traces management"""

    def __init__(self, collector_url: str, query_url: str, client: KuadrantClient = None):
        self.collector_url = collector_url
        self.client = client or KuadrantClient(verify=False)
        self.query = ApyProxy(query_url, session=self.client)

    def _get_traces(self, operation: str) -> Iterator[dict]:
        """Get traces from tracing client by operation name"""
        params = {"service": "authorino", "operation": operation}
        response = self.query.api.traces.get(params=params)
        return reversed(response.json()["data"])

    @backoff.on_predicate(backoff.fibo, lambda x: x is None, max_tries=5, jitter=None)
    def find_trace(self, operation: str, request_id: str) -> Optional[dict]:
        """Find trace in tracing client by operation and authorino request id"""
        for trace in self._get_traces(operation):  # pylint: disable=too-many-nested-blocks
            for span in trace["spans"]:
                if span["operationName"] == operation:
                    for tag in span["tags"]:
                        if tag["key"] == "authorino.request_id" and tag["value"] == request_id:
                            return trace
        return None

    def find_tagged_trace(self, operation: str, request_id: str, tag_key: str, tag_value: str) -> Optional[dict]:
        """Find trace in tracing client by operation, authorino request id and tag key-value pair"""
        if trace := self.find_trace(operation, request_id):
            for process in trace["processes"]:
                for proc_tag in trace["processes"][process]["tags"]:
                    if proc_tag["key"] == tag_key and proc_tag["value"] == tag_value:
                        return trace
        return None

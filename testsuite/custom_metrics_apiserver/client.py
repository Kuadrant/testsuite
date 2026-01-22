"""Client for interacting with the Custom Metrics API Server.

This module provides a client for writing metrics to the Custom Metrics API Server,
which can be used to set custom metrics for Kubernetes resources.
"""

import httpx


class CustomMetricsApiServerClient(httpx.Client):
    """Client for the Custom Metrics API Server."""

    def __init__(self, url: str) -> None:
        """Initialize the client with base URL and default headers"""
        super().__init__(base_url=url, verify=False, headers={"Content-Type": "application/json"})

    def write_metric(self, namespace: str, resource_type: str, name: str, metric: str, value: int) -> int:
        """Write a metric value to the Custom Metrics API Server"""
        endpoint = f"/write-metrics/namespaces/{namespace}/{resource_type}/{name}/{metric}"

        response = self.post(endpoint, content=f"{value}")
        response.raise_for_status()
        return response.status_code

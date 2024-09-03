"""Kubernetes monitoring common objects"""

from dataclasses import dataclass


@dataclass
class MetricsEndpoint:
    """Dataclass for endpoint definition in ServiceMonitor Kubernetes object.
    It contains endpoint path and port to the exported metrics."""

    path: str = "/metrics"
    port: str = "http"
    interval: str = "30s"

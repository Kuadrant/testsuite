"""Kubernetes monitoring common objects"""

from dataclasses import dataclass


@dataclass
class Relabeling:
    """Dataclass for relabeling definition in ServiceMonitor Kubernetes object.
    It contains relabeling action, source labels, regex, replacement, and target label."""

    action: str = None
    sourceLabels: list[str] = None
    regex: str = None
    replacement: str = None
    targetLabel: str = None
    separator: str = None


@dataclass
class MetricsEndpoint:
    """Dataclass for endpoint definition in ServiceMonitor Kubernetes object.
    It contains endpoint path and port to the exported metrics."""

    path: str = "/metrics"
    port: str = "http"
    interval: str = "30s"
    relabelings: list[Relabeling] = None

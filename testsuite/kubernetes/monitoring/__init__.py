"""Kubernetes monitoring common objects"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Relabeling:
    """Dataclass for relabeling definition in ServiceMonitor Kubernetes object.
    It contains relabeling action, source labels, regex, replacement, and target label."""

    action: Optional[str] = None
    # pylint: disable=invalid-name
    sourceLabels: list[str] = field(default_factory=list)
    regex: Optional[str] = None
    replacement: Optional[str] = None
    # pylint: disable=invalid-name
    targetLabel: Optional[str] = None
    separator: Optional[str] = None


@dataclass
class MetricsEndpoint:
    """Dataclass for endpoint definition in ServiceMonitor Kubernetes object.
    It contains endpoint path and port to the exported metrics."""

    path: str = "/metrics"
    port: str = "http"
    interval: str = "30s"
    relabelings: list[Relabeling] = field(default_factory=list)

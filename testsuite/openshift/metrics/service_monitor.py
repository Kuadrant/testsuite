"""Module implements Service Monitor CR for OpenShift"""
from dataclasses import dataclass

from testsuite.utils import asdict
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift import OpenShiftObject


@dataclass
class MetricsEndpoint:
    """Dataclass for endpoint definition in Service Monitor OpenShift object.
    It contains endpoint path and port to the exported metrics."""

    path: str = "/metrics"
    port: str = "http"


class ServiceMonitor(OpenShiftObject):
    """Represents Service Monitor object for OpenShift"""

    @classmethod
    def create_instance(
        cls,
        openshift: OpenShiftClient,
        name: str,
        endpoints: list[MetricsEndpoint],
        match_labels: dict[str, str],
        labels: dict[str, str] = None,
    ):
        """Creates new instance of ServiceMonitor"""
        model = {
            "apiVersion": "monitoring.coreos.com/v1",
            "kind": "ServiceMonitor",
            "metadata": {
                "name": name,
                "labels": labels,
            },
            "spec": {
                "endpoints": [asdict(e) for e in endpoints],
                "selector": {
                    "matchLabels": match_labels,
                },
            },
        }

        return cls(model, context=openshift.context)

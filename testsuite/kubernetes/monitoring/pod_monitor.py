"""Module implements Pod Monitor CR"""

from testsuite.kubernetes import KubernetesObject
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kubernetes.monitoring import MetricsEndpoint
from testsuite.utils import asdict


class PodMonitor(KubernetesObject):
    """Represents Pod Monitor object for OpenShift"""

    @classmethod
    def create_instance(
        cls,
        cluster: KubernetesClient,
        name: str,
        endpoints: list[MetricsEndpoint],
        match_labels: dict[str, str],
        labels: dict[str, str] = None,
    ):
        """Creates new instance of ServiceMonitor"""
        model = {
            "apiVersion": "monitoring.coreos.com/v1",
            "kind": "PodMonitor",
            "metadata": {
                "name": name,
                "labels": labels,
            },
            "spec": {
                "podMetricsEndpoints": [asdict(e) for e in endpoints],
                "selector": {
                    "matchLabels": match_labels,
                },
            },
        }

        return cls(model, context=cluster.context)

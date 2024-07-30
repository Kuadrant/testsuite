"""Module implements Service Monitor CR"""

from testsuite.kubernetes.monitoring import MetricsEndpoint
from testsuite.utils import asdict
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kubernetes import KubernetesObject


class ServiceMonitor(KubernetesObject):
    """Kubernetes ServiceMonitor object"""

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

        return cls(model, context=cluster.context)

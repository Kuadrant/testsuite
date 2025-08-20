"""Horizontal Pod Autoscaler related objects"""

from testsuite.kubernetes import KubernetesObject
from testsuite.kubernetes.deployment import Deployment


class HorizontalPodAutoscaler(KubernetesObject):
    """Kubernetes Horizontal Pod Autoscaler object"""

    @classmethod
    def create_instance(
        cls,
        cluster,
        name,
        deployment: Deployment,
        metrics: list[dict],
        labels: dict[str, str] = None,
        min_replicas: int = 1,
        max_replicas: int = 10,
    ):
        """Creates new instance of Horizontal Pod Autoscaler"""
        model: dict = {
            "kind": "HorizontalPodAutoscaler",
            "apiVersion": "autoscaling/v2",
            "metadata": {
                "name": name,
                "labels": labels,
            },
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": deployment.name(),
                },
                "minReplicas": min_replicas,
                "maxReplicas": max_replicas,
                "metrics": metrics,
            },
        }
        return cls(model, context=cluster.context)

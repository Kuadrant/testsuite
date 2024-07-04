"""Service Account object for OpenShift"""

from testsuite.kubernetes import KubernetesObject
from testsuite.kubernetes.client import KubernetesClient


class ServiceAccount(KubernetesObject):
    """Service account object for OpenShift"""

    def __init__(self, cluster: KubernetesClient, model: dict):
        self.cluster = cluster
        super().__init__(model, context=cluster.context)

    @classmethod
    def create_instance(cls, openshift: KubernetesClient, name: str, labels: dict[str, str] = None):
        """Creates new instance of service account"""
        model = {
            "kind": "ServiceAccount",
            "apiVersion": "v1",
            "metadata": {
                "name": name,
                "labels": labels,
            },
        }

        return cls(openshift, model)

    def get_auth_token(self, audiences: list[str] = None) -> str:
        """Requests and returns bound token for service account"""
        audiences_args = [f"--audience={a}" for a in audiences or []]
        return self.cluster.do_action("create", "token", self.name(), *audiences_args).out().strip()

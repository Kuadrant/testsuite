"""Module for DNSPolicy related classes"""

from testsuite.gateway import Referencable
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kuadrant.policy import Policy


class DNSPolicy(Policy):
    """DNSPolicy object"""

    @classmethod
    def create_instance(
        cls,
        cluster: KubernetesClient,
        name: str,
        parent: Referencable,
        labels: dict[str, str] = None,
    ):
        """Creates new instance of DNSPolicy"""

        model: dict = {
            "apiVersion": "kuadrant.io/v1alpha1",
            "kind": "DNSPolicy",
            "metadata": {"name": name, "labels": labels},
            "spec": {"targetRef": parent.reference, "routingStrategy": "simple"},
        }

        return cls(model, context=cluster.context)

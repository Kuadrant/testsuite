"""Module for DNSPolicy related classes"""

from dataclasses import dataclass

from testsuite.gateway import Referencable
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kuadrant.policy import Policy
from testsuite.utils import asdict


@dataclass
class LoadBalancing:
    """Dataclass for DNSPolicy load-balancing spec"""

    default_geo: str
    default_weight: int

    def asdict(self):
        """Custom asdict due to nested structure."""
        return {
            "geo": {"defaultGeo": self.default_geo},
            "weighted": {"defaultWeight": self.default_weight},
        }


class DNSPolicy(Policy):
    """DNSPolicy object"""

    @classmethod
    def create_instance(
        cls,
        cluster: KubernetesClient,
        name: str,
        parent: Referencable,
        provider_secret_name: str,
        load_balancing: LoadBalancing = None,
        labels: dict[str, str] = None,
    ):
        """Creates new instance of DNSPolicy"""

        model: dict = {
            "apiVersion": "kuadrant.io/v1alpha1",
            "kind": "DNSPolicy",
            "metadata": {"name": name, "labels": labels},
            "spec": {
                "targetRef": parent.reference,
                "providerRefs": [{"name": provider_secret_name}],
                "routingStrategy": "simple",
            },
        }

        if load_balancing:
            model["spec"]["routingStrategy"] = "loadbalanced"
            model["spec"]["loadBalancing"] = asdict(load_balancing)

        return cls(model, context=cluster.context)

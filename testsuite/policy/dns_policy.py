"""Module for DNSPolicy related classes"""

from testsuite.gateway import Referencable
from testsuite.openshift.client import OpenShiftClient
from testsuite.policy import Policy


class DNSPolicy(Policy):
    """DNSPolicy object"""

    @classmethod
    def create_instance(
        cls,
        openshift: OpenShiftClient,
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

        return cls(model, context=openshift.context)

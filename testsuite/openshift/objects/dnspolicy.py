"""Module for DNSPolicy related classes"""
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects import OpenShiftObject
from testsuite.openshift.objects.gateway_api import Referencable


class DNSPolicy(OpenShiftObject):
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

        model = {
            "apiVersion": "kuadrant.io/v1alpha1",
            "kind": "DNSPolicy",
            "metadata": {"name": name, "labels": labels},
            "spec": {"targetRef": parent.reference},
        }

        return cls(model, context=openshift.context)

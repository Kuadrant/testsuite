"""Module for TLSPolicy related classes"""
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects import OpenShiftObject
from testsuite.openshift.objects.gateway_api import Referencable


class TLSPolicy(OpenShiftObject):
    """TLSPolicy object"""

    @classmethod
    def create_instance(
        cls,
        openshift: OpenShiftClient,
        name: str,
        parent: Referencable,
        issuer: Referencable,
        labels: dict[str, str] = None,
    ):
        """Creates new instance of TLSPolicy"""

        model = {
            "apiVersion": "kuadrant.io/v1alpha1",
            "kind": "TLSPolicy",
            "metadata": {"name": name, "labels": labels},
            "spec": {
                "targetRef": parent.reference,
                "issuerRef": issuer.reference,
            },
        }

        return cls(model, context=openshift.context)

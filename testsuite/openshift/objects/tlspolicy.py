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
        commonName: str = None,
        duration: str = None,
        usages: list[str] = None,
        algorithm: str = None,
        key_size: int = None,
    ):  # pylint: disable=invalid-name
        """Creates new instance of TLSPolicy"""

        model = {
            "apiVersion": "kuadrant.io/v1alpha1",
            "kind": "TLSPolicy",
            "metadata": {"name": name, "labels": labels},
            "spec": {
                "targetRef": parent.reference,
                "issuerRef": issuer.reference,
                "commonName": commonName,
                "duration": duration,
                "usages": usages,
                "privateKey": {
                    "algorithm": algorithm,
                    "size": key_size,
                },
            },
        }

        return cls(model, context=openshift.context)

    def __setitem__(self, key, value):
        self.model.spec[key] = value

    def __getitem__(self, key):
        return self.model.spec[key]

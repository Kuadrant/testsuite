"""Module containing classes related to Auth Policy"""
from typing import Dict

from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects.auth_config import AuthConfig
from testsuite.openshift.objects.gateway_api import Referencable


class AuthPolicy(AuthConfig):
    """AuthPolicy object, it serves as Kuadrants AuthConfig"""

    @property
    def auth_section(self):
        return self.model.spec.setdefault("authScheme", {})

    # pylint: disable=unused-argument
    @classmethod
    def create_instance(  # type: ignore
        cls,
        openshift: OpenShiftClient,
        name,
        route: Referencable,
        labels: Dict[str, str] = None,
        hostnames=None,
    ):
        """Creates base instance"""
        model: Dict = {
            "apiVersion": "kuadrant.io/v1beta1",
            "kind": "AuthPolicy",
            "metadata": {
                "name": name,
                "namespace": openshift.project,
            },
            "spec": {
                "targetRef": route.reference,
            },
        }

        if labels is not None:
            model["metadata"]["labels"] = labels

        return cls(model, context=openshift.context)

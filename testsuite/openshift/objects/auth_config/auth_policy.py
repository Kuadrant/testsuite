"""Module containing classes related to Auth Policy"""
from typing import Dict

from testsuite.objects import Rule, asdict
from testsuite.objects.gateway import Referencable
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects import modify
from testsuite.openshift.objects.auth_config import AuthConfig


class AuthPolicy(AuthConfig):
    """AuthPolicy object, it serves as Kuadrants AuthConfig"""

    @property
    def auth_section(self):
        return self.model.spec.setdefault("rules", {})

    # pylint: disable=unused-argument
    @classmethod
    def create_instance(  # type: ignore
        cls,
        openshift: OpenShiftClient,
        name,
        route: Referencable,
        labels: Dict[str, str] = None,
    ):
        """Creates base instance"""
        model: Dict = {
            "apiVersion": "kuadrant.io/v1beta2",
            "kind": "AuthPolicy",
            "metadata": {"name": name, "namespace": openshift.project, "labels": labels},
            "spec": {
                "targetRef": route.reference,
            },
        }

        return cls(model, context=openshift.context)

    @modify
    def add_rule(self, when: list[Rule]):
        """Add rule for the skip of entire AuthPolicy"""
        self.model.spec.setdefault("when", [])
        self.model.spec["when"].extend([asdict(x) for x in when])

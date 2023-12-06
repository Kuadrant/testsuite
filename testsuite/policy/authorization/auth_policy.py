"""Module containing classes related to AuthPolicy"""
from typing import Dict, TYPE_CHECKING

from testsuite.utils import asdict
from testsuite.gateway import Referencable
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift import modify
from .auth_config import AuthConfig

if TYPE_CHECKING:
    from . import Rule


class AuthPolicy(AuthConfig):
    """AuthPolicy object, it serves as Kuadrants AuthConfig"""

    @property
    def auth_section(self):
        return self.model.spec.setdefault("rules", {})

    @classmethod
    def create_instance(
        cls,
        openshift: OpenShiftClient,
        name,
        target: Referencable,
        labels: Dict[str, str] = None,
    ):
        """Creates base instance"""
        model: Dict = {
            "apiVersion": "kuadrant.io/v1beta2",
            "kind": "AuthPolicy",
            "metadata": {"name": name, "namespace": openshift.project, "labels": labels},
            "spec": {
                "targetRef": target.reference,
                "rules": {},
            },
        }

        return cls(model, context=openshift.context)

    @modify
    def add_rule(self, when: list["Rule"]):
        """Add rule for the skip of entire AuthPolicy"""
        self.model.spec.setdefault("when", [])
        self.model.spec["when"].extend([asdict(x) for x in when])

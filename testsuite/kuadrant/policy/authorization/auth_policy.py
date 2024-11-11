"""Module containing classes related to AuthPolicy"""

from functools import cached_property
from typing import Dict, TYPE_CHECKING

from testsuite.gateway import Referencable
from testsuite.kubernetes import modify
from testsuite.kubernetes.client import KubernetesClient
from testsuite.utils import asdict
from .auth_config import AuthConfig
from .sections import ResponseSection
from .. import Policy
from . import Pattern

if TYPE_CHECKING:
    from . import Rule


class AuthPolicy(Policy, AuthConfig):
    """AuthPolicy object, it serves as Kuadrants AuthConfig"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spec_section = None

    @classmethod
    def create_instance(
        cls,
        cluster: KubernetesClient,
        name,
        target: Referencable,
        labels: Dict[str, str] = None,
    ):
        """Creates base instance"""
        model: Dict = {
            "apiVersion": "kuadrant.io/v1beta3",
            "kind": "AuthPolicy",
            "metadata": {"name": name, "namespace": cluster.project, "labels": labels},
            "spec": {
                "targetRef": target.reference,
            },
        }

        return cls(model, context=cluster.context)

    @modify
    def add_rule(self, when: list["Rule"]):
        """Add rule for the skip of entire AuthPolicy"""
        self.model.spec.setdefault("when", [])
        self.model.spec["when"].extend([asdict(x) for x in when])

    @property
    def auth_section(self):
        if self.spec_section is None:
            self.spec_section = self.model.spec

        spec_section = self.spec_section
        self.spec_section = None
        return spec_section.setdefault("rules", {})

    @cached_property
    def responses(self) -> ResponseSection:
        """Gives access to response settings"""
        return ResponseSection(self, "response", "filters")

    @property
    def defaults(self):
        """Add new rule into the `defaults` AuthPolicy section"""
        self.spec_section = self.model.spec.setdefault("defaults", {})
        return self

    @property
    def overrides(self):
        """Add new rule into the `overrides` AuthPolicy section"""
        self.spec_section = self.model.spec.setdefault("overrides", {})
        return self

    @modify
    def add_patterns(self, patterns: dict[str, list[Pattern]]):
        """Add named pattern-matching expressions to be referenced in other "when" rules."""
        self.model.spec.setdefault("patterns", {})
        for key, value in patterns.items():
            self.model.spec["patterns"].update({key: {"allOf": [asdict(x) for x in value]}})

"""Module containing classes related to AuthPolicy"""

from functools import cached_property
from typing import Dict

from testsuite.gateway import Referencable
from testsuite.kubernetes import modify
from testsuite.kubernetes.client import KubernetesClient
from testsuite.utils import asdict
from .auth_config import AuthConfig
from .sections import ResponseSection
from .. import Policy, CelPredicate, SectionContext
from . import Pattern


class AuthPolicySectionContext(SectionContext, AuthConfig):
    """Context for working within a defaults/overrides section of AuthPolicy"""

    @property
    def model(self):
        """Delegate to policy's model"""
        return self._policy.model

    @property
    def auth_section(self):
        """Override to point to the defaults/overrides section"""
        return self.model.spec.setdefault(self._section_name, {}).setdefault("rules", {})


class AuthPolicy(Policy, AuthConfig):
    """AuthPolicy object, it serves as Kuadrants AuthConfig"""

    @classmethod
    def create_instance(
        cls,
        cluster: KubernetesClient,
        name,
        target: Referencable,
        labels: Dict[str, str] = None,
        section_name: str = None,
    ):
        """Creates base instance"""
        model: Dict = {
            "apiVersion": "kuadrant.io/v1",
            "kind": "AuthPolicy",
            "metadata": {"name": name, "namespace": cluster.project, "labels": labels},
            "spec": {
                "targetRef": target.reference,
            },
        }
        if section_name:
            model["spec"]["targetRef"]["sectionName"] = section_name

        return cls(model, context=cluster.context)

    @property
    def defaults(self):
        """Work within the defaults section"""
        return AuthPolicySectionContext(self, "defaults")

    @property
    def overrides(self):
        """Work within the overrides section"""
        return AuthPolicySectionContext(self, "overrides")

    @modify
    def add_rule(self, when: list[CelPredicate]):
        """Add rule for the skip of entire AuthPolicy"""
        self.model.spec.setdefault("when", [])
        self.model.spec["when"].extend([asdict(x) for x in when])

    @property
    def auth_section(self):
        """Rules section for top-level spec (implicit defaults)"""
        return self.model.spec.setdefault("rules", {})

    @cached_property
    def responses(self) -> ResponseSection:
        """Gives access to response settings"""
        return ResponseSection(self, "response", "filters")

    @modify
    def add_patterns(self, patterns: dict[str, list[Pattern]]):
        """Add named pattern-matching expressions to be referenced in other "when" rules."""
        self.model.spec.setdefault("patterns", {})
        for key, value in patterns.items():
            self.model.spec["patterns"].update({key: {"allOf": [asdict(x) for x in value]}})

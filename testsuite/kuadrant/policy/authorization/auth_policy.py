"""Module containing classes related to AuthPolicy"""

from functools import cached_property
from typing import Dict

from testsuite.gateway import Referencable
from testsuite.kubernetes import modify
from testsuite.kubernetes.client import KubernetesClient
from testsuite.utils import asdict
from .auth_config import AuthConfig
from .sections import ResponseSection
from .. import Policy, CelPredicate, Section
from . import Pattern


class AuthSection(Section, AuthConfig):
    """Section that combines base Section with AuthConfig methods"""

    @property
    def model(self):
        """Delegate to parent policy's model for AuthConfig compatibility"""
        return self.obj.model

    @property
    def auth_section(self):
        """Returns section where auth rules should be added"""
        return self.get_section("rules")


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
        return AuthSection(self, "defaults")

    @property
    def overrides(self):
        """Work within the overrides section"""
        return AuthSection(self, "overrides")

    @modify
    def add_rule(self, when: list[CelPredicate]):
        """Add rule for the skip of entire AuthPolicy - uses generic add_to_spec helper"""
        existing = self.model.spec.get("when", [])
        # Extend existing rules
        extended = existing + [asdict(x) for x in when]
        section = Section(self, None)
        section.add_to_spec(self.model.spec, when=extended)

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
        """Add named pattern-matching expressions to be referenced in other "when" rules - uses generic helper"""
        patterns_spec = {}
        for key, value in patterns.items():
            patterns_spec[key] = {"allOf": [asdict(x) for x in value]}

        existing = self.model.spec.get("patterns", {})
        existing.update(patterns_spec)
        section = Section(self, None)
        section.add_to_spec(self.model.spec, patterns=existing)

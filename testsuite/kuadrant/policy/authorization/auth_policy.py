"""Module containing classes related to AuthPolicy"""

from functools import cached_property
from typing import Dict

from testsuite.gateway import Referencable
from testsuite.kubernetes import modify
from testsuite.kubernetes.client import KubernetesClient
from testsuite.utils import asdict
from .auth_config import AuthConfig
from .sections import ResponseSection
from .. import Policy, CelPredicate, Strategy
from . import Pattern


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

    @modify
    def add_rule(self, when: list[CelPredicate]):
        """Add rule for the skip of entire AuthPolicy"""
        self.model.spec.setdefault("when", [])
        self.model.spec["when"].extend([asdict(x) for x in when])

    @modify
    def strategy(self, strategy: Strategy) -> None:
        """Add strategy type to default or overrides spec"""
        if self.spec_section is None:
            raise TypeError("Strategy can only be set on defaults or overrides")

        if isinstance(self.spec_section, str):
            # String marker - create the section now
            section = self.model.spec.setdefault(self.spec_section, {})
        else:
            section = self.spec_section

        section["strategy"] = strategy.value
        self.spec_section = None

    @property
    def auth_section(self):
        """Returns the rules section for adding auth configuration"""
        if self.spec_section is None:
            # Implicit mode - use model.spec directly
            spec_section = self.model.spec
        elif isinstance(self.spec_section, str):
            # String marker ("defaults" or "overrides") - create the section now
            spec_section = self.model.spec.setdefault(self.spec_section, {})
        else:
            # Already a dict (shouldn't happen with new code but keep for compatibility)
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
        # Don't create the dict yet - only mark which section to use
        # The dict will be created when auth_section is called
        self.spec_section = "defaults"
        return self

    @property
    def overrides(self):
        """Add new rule into the `overrides` AuthPolicy section"""
        # Don't create the dict yet - only mark which section to use
        # The dict will be created when auth_section is called
        self.spec_section = "overrides"
        return self

    @modify
    def add_patterns(self, patterns: dict[str, list[Pattern]]):
        """Add named pattern-matching expressions to be referenced in other "when" rules."""
        self.model.spec.setdefault("patterns", {})
        for key, value in patterns.items():
            self.model.spec["patterns"].update({key: {"allOf": [asdict(x) for x in value]}})

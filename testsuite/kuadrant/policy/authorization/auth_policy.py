"""Module containing classes related to AuthPolicy"""

from functools import cached_property
from typing import Dict

from testsuite.gateway import Referencable
from testsuite.kubernetes import modify
from testsuite.kubernetes.client import KubernetesClient
from testsuite.utils import asdict
from .auth_config import AuthConfig
from .sections import ResponseSection, IdentitySection, AuthorizationSection, MetadataSection
from .auth_policy_spec import AuthPolicySpec, MergeableAuthPolicySpec
from .. import Policy, CelPredicate
from . import Pattern


class AuthPolicy(Policy, AuthConfig):
    """AuthPolicy object, it serves as Kuadrants AuthConfig"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize the spec structure from the model
        target_ref = self.model.spec.get("targetRef", {})
        self.spec = AuthPolicySpec(self, target_ref)

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
    def defaults(self) -> MergeableAuthPolicySpec:
        """
        Returns the defaults section, creating it lazily on first access.

        Usage:
            auth.defaults.identity.add_oidc(...)
            auth.defaults.strategy(Strategy.MERGE)

        Note: To check if defaults exists without creating it, use: `policy.spec.defaults is None`
        """
        if self.spec.defaults is None:
            self.spec.defaults = MergeableAuthPolicySpec(self)
        return self.spec.defaults

    @property
    def overrides(self) -> MergeableAuthPolicySpec:
        """
        Returns the overrides section, creating it lazily on first access.

        Usage:
            auth.overrides.identity.add_oidc(...)
            auth.overrides.strategy(Strategy.MERGE)

        Note: To check if overrides exists without creating it, use: `policy.spec.overrides is None`
        """
        if self.spec.overrides is None:
            self.spec.overrides = MergeableAuthPolicySpec(self)
        return self.spec.overrides

    @modify
    def add_rule(self, when: list[CelPredicate]):
        """Add rule for the skip of entire AuthPolicy"""
        self.model.spec.setdefault("when", [])
        self.model.spec["when"].extend([asdict(x) for x in when])

    @property
    def auth_section(self):
        """Returns the rules section from the active spec (implicit/defaults/overrides)."""
        return self.spec.proper().rules

    @cached_property
    def identity(self) -> IdentitySection:
        """Gives access to identity settings"""
        return self.spec.proper().identity

    @cached_property
    def authorization(self) -> AuthorizationSection:
        """Gives access to authorization settings"""
        return self.spec.proper().authorization

    @cached_property
    def metadata(self) -> MetadataSection:
        """Gives access to metadata settings"""
        return self.spec.proper().metadata

    @cached_property
    def responses(self) -> ResponseSection:
        """Gives access to response settings"""
        return self.spec.proper().responses

    def _sync_spec_to_model(self):
        """Sync the spec object to model.spec dict before commit."""
        self.model.spec = self.spec.to_dict()

    def commit(self):
        """Commit the policy to Kubernetes after syncing spec to model."""
        self._sync_spec_to_model()
        return super().commit()

    @modify
    def add_patterns(self, patterns: dict[str, list[Pattern]]):
        """Add named pattern-matching expressions to be referenced in other "when" rules."""
        self.model.spec.setdefault("patterns", {})
        for key, value in patterns.items():
            self.model.spec["patterns"].update({key: {"allOf": [asdict(x) for x in value]}})

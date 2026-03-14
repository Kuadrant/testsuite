"""RateLimitPolicy related objects"""

import time
from dataclasses import dataclass
from typing import Iterable

from testsuite.gateway import Referencable
from testsuite.kubernetes import modify
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kuadrant.policy import Policy, CelPredicate, CelExpression
from testsuite.kuadrant.policy.rate_limit_spec import (
    RateLimitPolicySpec,
    MergeableRateLimitPolicySpec,
)


@dataclass
class Limit:
    """Limit dataclass"""

    limit: int
    window: str


class RateLimitPolicy(Policy):
    """RateLimitPolicy (or RLP for short) object, used for applying rate limiting rules to a Gateway/HTTPRoute"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize the spec structure from the model
        target_ref = self.model.spec.get("targetRef", {})
        self.spec = RateLimitPolicySpec(target_ref)

    @classmethod
    def create_instance(
        cls,
        cluster: KubernetesClient,
        name,
        target: Referencable,
        section_name: str = None,
        labels: dict[str, str] = None,
    ):
        """Creates new instance of RateLimitPolicy"""
        model: dict = {
            "apiVersion": "kuadrant.io/v1",
            "kind": "RateLimitPolicy",
            "metadata": {"name": name, "namespace": cluster.project, "labels": labels},
            "spec": {
                "targetRef": target.reference,
            },
        }
        if section_name:
            model["spec"]["targetRef"]["sectionName"] = section_name

        return cls(model, context=cluster.context)

    @property
    def defaults(self) -> MergeableRateLimitPolicySpec:
        """
        Returns the defaults section, creating it lazily on first access.

        Usage:
            rlp.defaults.add_limit("basic", [Limit(5, "10s")])
            rlp.defaults.strategy = Strategy.MERGE

        Note: To check if defaults exists without creating it, use: `policy.spec.defaults is None`
        """
        if self.spec.defaults is None:
            self.spec.defaults = MergeableRateLimitPolicySpec()
        return self.spec.defaults

    @property
    def overrides(self) -> MergeableRateLimitPolicySpec:
        """
        Returns the overrides section, creating it lazily on first access.

        Usage:
            rlp.overrides.add_limit("override", [Limit(10, "10s")])
            rlp.overrides.strategy = Strategy.MERGE

        Note: To check if overrides exists without creating it, use: `policy.spec.overrides is None`
        """
        if self.spec.overrides is None:
            self.spec.overrides = MergeableRateLimitPolicySpec()
        return self.spec.overrides

    @modify
    def add_limit(
        self,
        name,
        limits: Iterable[Limit],
        when: list[CelPredicate] = None,
        counters: list[CelExpression] = None,
    ):
        """
        Add a limit to the implicit (bare) spec.

        This is for backward compatibility and adds limits directly to the policy
        without using defaults or overrides.
        """
        self.spec.proper().add_limit(name, limits, when, counters)

    def _sync_spec_to_model(self):
        """Sync the spec object to model.spec dict before commit."""
        self.model.spec = self.spec.to_dict()

    def commit(self):
        """Commit the policy to Kubernetes after syncing spec to model."""
        self._sync_spec_to_model()
        return super().commit()

    def wait_for_ready(self):
        """Wait for RLP to be enforced"""
        super().wait_for_ready()
        # Even after enforced condition RLP requires a short sleep
        time.sleep(5)

"""RateLimitPolicy related objects"""

import time
from dataclasses import dataclass
from typing import Iterable

from testsuite.gateway import Referencable
from testsuite.kubernetes import modify
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kuadrant.policy import Policy, CelPredicate, CelExpression, Strategy
from testsuite.utils import asdict


@dataclass
class Limit:
    """Limit dataclass"""

    limit: int
    window: str


class RateLimitPolicy(Policy):
    """RateLimitPolicy (or RLP for short) object, used for applying rate limiting rules to a Gateway/HTTPRoute"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spec_section = None

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

    @modify
    def add_limit(
        self,
        name,
        limits: Iterable[Limit],
        when: list[CelPredicate] = None,
        counters: list[CelExpression] = None,
    ):
        """Add another limit"""
        limit: dict = {
            "rates": [asdict(limit) for limit in limits],
        }
        if when:
            limit["when"] = [asdict(rule) for rule in when]
        if counters:
            limit["counters"] = [asdict(rule) for rule in counters]

        if self.spec_section is None:
            # Implicit mode - use model.spec directly
            spec_section = self.model.spec
        elif isinstance(self.spec_section, str):
            # String marker ("defaults" or "overrides") - create the section now
            spec_section = self.model.spec.setdefault(self.spec_section, {})
        else:
            # Already a dict (shouldn't happen with new code but keep for compatibility)
            spec_section = self.spec_section

        spec_section.setdefault("limits", {})[name] = limit
        self.spec_section = None

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
    def defaults(self):
        """Add new rule into the `defaults` RateLimitPolicy section"""
        # Don't create the dict yet - only mark which section to use
        # The dict will be created when add_limit or strategy is called
        self.spec_section = "defaults"
        return self

    @property
    def overrides(self):
        """Add new rule into the `overrides` RateLimitPolicy section"""
        # Don't create the dict yet - only mark which section to use
        # The dict will be created when add_limit or strategy is called
        self.spec_section = "overrides"
        return self

    def wait_for_ready(self):
        """Wait for RLP to be enforced"""
        super().wait_for_ready()
        # Even after enforced condition RLP requires a short sleep
        time.sleep(5)

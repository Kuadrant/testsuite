"""RateLimitPolicy related objects"""

import time
from dataclasses import dataclass
from typing import Iterable

from testsuite.gateway import Referencable
from testsuite.kubernetes import modify
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kuadrant.policy import Policy, CelPredicate, CelExpression, Section
from testsuite.utils import asdict


@dataclass
class Limit:
    """Limit dataclass"""

    limit: int
    window: str


class RateLimitSection(Section):
    """Section for rate limit policies - adds rate limit specific methods"""

    @modify
    def add_limit(
        self,
        name,
        limits: Iterable[Limit],
        when: list[CelPredicate] = None,
        counters: list[CelExpression] = None,
    ):
        """Add a rate limit to this section"""
        limit: dict = {
            "rates": [asdict(lim) for lim in limits],
        }
        self.add_to_spec(limit, when=when, counters=counters)
        target = self.get_section()
        target.setdefault("limits", {})[name] = limit
        return self


class RateLimitPolicy(Policy):
    """RateLimitPolicy (or RLP for short) object, used for applying rate limiting rules to a Gateway/HTTPRoute"""

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
    def defaults(self):
        """Work within the defaults section"""
        return RateLimitSection(self, "defaults")

    @property
    def overrides(self):
        """Work within the overrides section"""
        return RateLimitSection(self, "overrides")

    @modify
    def add_limit(
        self,
        name,
        limits: Iterable[Limit],
        when: list[CelPredicate] = None,
        counters: list[CelExpression] = None,
    ):
        """Add limit to top-level spec (implicit defaults)"""
        # Use RateLimitSection to avoid duplication
        section = RateLimitSection(self, None)
        return section.add_limit(name, limits, when, counters)

    def wait_for_ready(self):
        """Wait for RLP to be enforced"""
        super().wait_for_ready()
        # Even after enforced condition RLP requires a short sleep
        time.sleep(5)

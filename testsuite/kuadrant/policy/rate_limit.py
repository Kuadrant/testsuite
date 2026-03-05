"""RateLimitPolicy related objects"""

import time
from dataclasses import dataclass
from typing import Iterable

from testsuite.gateway import Referencable
from testsuite.kubernetes import modify
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kuadrant.policy import Policy, CelPredicate, CelExpression, SectionContext
from testsuite.utils import asdict


@dataclass
class Limit:
    """Limit dataclass"""

    limit: int
    window: str


class RateLimitSectionContext(SectionContext):
    """Context for working within a defaults/overrides section of RateLimitPolicy"""

    def add_limit(
        self,
        name,
        limits: Iterable[Limit],
        when: list[CelPredicate] = None,
        counters: list[CelExpression] = None,
    ):
        """Add limit to this section"""
        limit: dict = {
            "rates": [asdict(limit) for limit in limits],
        }
        if when:
            limit["when"] = [asdict(rule) for rule in when]
        if counters:
            limit["counters"] = [asdict(rule) for rule in counters]

        target = self._policy.model.spec.setdefault(self._section_name, {})
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
        return RateLimitSectionContext(self, "defaults")

    @property
    def overrides(self):
        """Work within the overrides section"""
        return RateLimitSectionContext(self, "overrides")

    @modify
    def add_limit(
        self,
        name,
        limits: Iterable[Limit],
        when: list[CelPredicate] = None,
        counters: list[CelExpression] = None,
    ):
        """Add limit to top-level spec (implicit defaults)"""
        limit: dict = {
            "rates": [asdict(limit) for limit in limits],
        }
        if when:
            limit["when"] = [asdict(rule) for rule in when]
        if counters:
            limit["counters"] = [asdict(rule) for rule in counters]

        self.model.spec.setdefault("limits", {})[name] = limit

    def wait_for_ready(self):
        """Wait for RLP to be enforced"""
        super().wait_for_ready()
        # Even after enforced condition RLP requires a short sleep
        time.sleep(5)

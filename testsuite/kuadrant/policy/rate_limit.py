"""RateLimitPolicy related objects"""

import time
from dataclasses import dataclass
from typing import Iterable

from testsuite.gateway import Referencable
from testsuite.kubernetes import modify
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kuadrant.policy import Policy, CelPredicate, CelExpression
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
    def create_instance(cls, cluster: KubernetesClient, name, target: Referencable, labels: dict[str, str] = None):
        """Creates new instance of RateLimitPolicy"""
        model = {
            "apiVersion": "kuadrant.io/v1",
            "kind": "RateLimitPolicy",
            "metadata": {"name": name, "labels": labels},
            "spec": {
                "targetRef": target.reference,
            },
        }

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
            self.spec_section = self.model.spec

        self.spec_section.setdefault("limits", {})[name] = limit
        self.spec_section = None

    @property
    def defaults(self):
        """Add new rule into the `defaults` RateLimitPolicy section"""
        self.spec_section = self.model.spec.setdefault("defaults", {})
        return self

    @property
    def overrides(self):
        """Add new rule into the `overrides` RateLimitPolicy section"""
        self.spec_section = self.model.spec.setdefault("overrides", {})
        return self

    def wait_for_ready(self):
        """Wait for RLP to be enforced"""
        super().wait_for_ready()
        # Even after enforced condition RLP requires a short sleep
        time.sleep(5)

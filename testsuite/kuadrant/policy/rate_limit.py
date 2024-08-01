"""RateLimitPolicy related objects"""

import time
from dataclasses import dataclass
from typing import Iterable, Literal, Optional, List

from testsuite.gateway import Referencable, RouteMatch
from testsuite.kubernetes import modify
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kuadrant.policy import Policy
from testsuite.kuadrant.policy.authorization import Rule
from testsuite.utils import asdict


@dataclass
class Limit:
    """Limit dataclass"""

    limit: int
    duration: int
    unit: Literal["second", "minute", "day"] = "second"


@dataclass
class RouteSelector:
    """
    RouteSelector is an object composed of a set of HTTPRouteMatch objects (from Gateway API -
    HTTPPathMatch, HTTPHeaderMatch, HTTPQueryParamMatch, HTTPMethodMatch),
    and an additional hostnames field.
    https://docs.kuadrant.io/kuadrant-operator/doc/reference/route-selectors/#routeselector
    """

    matches: Optional[list[RouteMatch]] = None
    hostnames: Optional[list[str]] = None

    def __init__(self, *matches: RouteMatch, hostnames: Optional[List[str]] = None):
        self.matches = list(matches) if matches else []
        self.hostnames = hostnames


class RateLimitPolicy(Policy):
    """RateLimitPolicy (or RLP for short) object, used for applying rate limiting rules to a Gateway/HTTPRoute"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spec_section = None

    @classmethod
    def create_instance(cls, cluster: KubernetesClient, name, target: Referencable, labels: dict[str, str] = None):
        """Creates new instance of RateLimitPolicy"""
        model = {
            "apiVersion": "kuadrant.io/v1beta2",
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
        when: Iterable[Rule] = None,
        counters: list[str] = None,
        route_selectors: Iterable[RouteSelector] = None,
    ):
        """Add another limit"""
        limit: dict = {
            "rates": [asdict(limit) for limit in limits],
        }
        if when:
            limit["when"] = [asdict(rule) for rule in when]
        if counters:
            limit["counters"] = counters
        if route_selectors:
            limit["routeSelectors"] = [asdict(rule) for rule in route_selectors]

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

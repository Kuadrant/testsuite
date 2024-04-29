"""RateLimitPolicy related objects"""

import time
from dataclasses import dataclass
from typing import Iterable, Literal, Optional, List

from openshift_client import timeout

from testsuite.gateway import Referencable, RouteMatch
from testsuite.openshift import modify
from testsuite.openshift.client import OpenShiftClient
from testsuite.policy import Policy
from testsuite.policy.authorization import Rule
from testsuite.utils import asdict, has_condition


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

    @classmethod
    def create_instance(cls, openshift: OpenShiftClient, name, target: Referencable, labels: dict[str, str] = None):
        """Creates new instance of RateLimitPolicy"""
        model = {
            "apiVersion": "kuadrant.io/v1beta2",
            "kind": "RateLimitPolicy",
            "metadata": {"name": name, "labels": labels},
            "spec": {
                "targetRef": target.reference,
                "limits": {},
            },
        }

        return cls(model, context=openshift.context)

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
        self.model.spec.limits[name] = limit

    def wait_for_ready(self):
        """Wait for RLP to be enforced"""
        with timeout(90):
            success, _, _ = self.self_selector().until_all(
                success_func=has_condition("Enforced", "True"),
                tolerate_failures=5,
            )
            assert success, f"{self.kind()} did not get ready in time"
        # Even after enforced condition RLP requires a short sleep
        time.sleep(5)

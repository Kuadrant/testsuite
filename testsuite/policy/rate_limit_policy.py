"""RateLimitPolicy related objects"""
from dataclasses import dataclass
from time import sleep
from typing import Iterable, Literal

import openshift as oc

from testsuite.policy.authorization import Pattern
from testsuite.utils import asdict
from testsuite.gateway import Referencable
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift import OpenShiftObject, modify


@dataclass
class Limit:
    """Limit dataclass"""

    limit: int
    duration: int
    unit: Literal["second", "minute", "day"] = "second"


class RateLimitPolicy(OpenShiftObject):
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
    def add_limit(self, name, limits: Iterable[Limit], when: Iterable[Pattern] = None, counters: list[str] = None):
        """Add another limit"""
        limit: dict = {
            "rates": [asdict(limit) for limit in limits],
        }
        if when:
            limit["when"] = [asdict(rule) for rule in when]
        if counters:
            limit["counters"] = counters
        self.model.spec.limits[name] = limit

    def commit(self):
        result = super().commit()

        # wait for RLP to be actually applied, conditions itself is not enough, sleep is needed
        def _policy_is_ready(obj):
            return "conditions" in obj.model.status and obj.model.status.conditions[0].status == "True"

        with oc.timeout(90):
            success, _, _ = self.self_selector().until_all(success_func=_policy_is_ready, tolerate_failures=5)
            assert success

        # https://github.com/Kuadrant/kuadrant-operator/issues/140
        sleep(90)

        return result

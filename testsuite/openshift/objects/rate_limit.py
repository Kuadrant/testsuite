"""RateLimitPolicy related objects"""
from time import sleep

import openshift as oc
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects import OpenShiftObject, modify
from testsuite.openshift.objects.gateway_api import Referencable


class RateLimitPolicy(OpenShiftObject):
    """RateLimitPolicy (or RLP for short) object, used for applying rate limiting rules to an Gateway/HTTPRoute"""

    @classmethod
    def create_instance(cls, openshift: OpenShiftClient, name, route: Referencable, labels: dict[str, str] = None):
        """Creates new instance of RateLimitPolicy"""
        model = {
            "apiVersion": "kuadrant.io/v1beta1",
            "kind": "RateLimitPolicy",
            "metadata": {"name": name, "namespace": openshift.project, "labels": labels},
            "spec": {
                "targetRef": route.reference,
                "rateLimits": [
                    {
                        "configurations": [
                            {"actions": [{"generic_key": {"descriptor_key": "limited", "descriptor_value": "1"}}]}
                        ]
                    }
                ],
            },
        }

        return cls(model, context=openshift.context)

    @modify
    def add_limit(self, max_value, seconds, conditions: list[str] = None):
        """Add another limit"""
        conditions = conditions or []
        limits = self.model.spec.rateLimits[0].setdefault("limits", [])
        limit = {"maxValue": max_value, "seconds": seconds, "conditions": conditions, "variables": []}
        limits.append(limit)

    def commit(self):
        result = super().commit()

        # wait for RLP to be actually applied, conditions itself is not enough, sleep is needed
        def _policy_is_ready(obj):
            return "conditions" in obj.model.status and obj.model.status.conditions[0].status == "True"

        with oc.timeout(90):
            success, _, _ = self.self_selector().until_all(success_func=_policy_is_ready, tolerate_failures=5)
            assert success

        # https://github.com/Kuadrant/kuadrant-operator/issues/140
        sleep(60)

        return result

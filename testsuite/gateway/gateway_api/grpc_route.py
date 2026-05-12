"""Module containing GRPCRoute class"""

import typing

from testsuite.gateway import Gateway, GatewayRoute, GRPCRouteMatch
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kubernetes import KubernetesObject, modify
from testsuite.kuadrant.policy import Policy
from testsuite.utils import asdict, check_condition

if typing.TYPE_CHECKING:
    from testsuite.backend import Backend


class GRPCRoute(KubernetesObject, GatewayRoute):
    """GRPCRoute object for Gateway API"""

    @classmethod
    def create_instance(
        cls,
        cluster: "KubernetesClient",
        name,
        gateway: Gateway,
        labels: dict[str, str] = None,
    ):
        """Creates new instance of GRPCRoute"""
        model = {
            "apiVersion": "gateway.networking.k8s.io/v1",
            "kind": "GRPCRoute",
            "metadata": {"name": name, "namespace": cluster.project, "labels": labels},
            "spec": {
                "parentRefs": [gateway.reference],
                "hostnames": [],
                "rules": [],
            },
        }

        return cls(model, context=cluster.context)

    def is_affected_by(self, policy: Policy):
        """Returns True, if affected by status is found within the object for the specific policy"""
        for condition_set in self.model.status.parents:
            if condition_set.controllerName == "kuadrant.io/policy-controller":
                for condition in condition_set.conditions:
                    if check_condition(
                        condition,
                        f"kuadrant.io/{policy.kind(lowercase=False)}Affected",
                        "True",
                        "Accepted",
                        f"Object affected by {policy.kind(lowercase=False)}",
                        f"{policy.namespace()}/{policy.name()}",
                    ):
                        return True
        return False

    @property
    def reference(self):
        return {
            "group": "gateway.networking.k8s.io",
            "kind": "GRPCRoute",
            "name": self.name(),
        }

    @property
    def hostnames(self):
        """Return all hostnames for this GRPCRoute"""
        return self.model.spec.hostnames

    @modify
    def add_hostname(self, hostname: str):
        """Adds hostname to the Route"""
        if hostname not in self.model.spec.hostnames:
            self.model.spec.hostnames.append(hostname)

    @modify
    def remove_hostname(self, hostname: str):
        """Removes hostname from the Route"""
        self.model.spec.hostnames.remove(hostname)

    @modify
    def remove_all_hostnames(self):
        """Removes all hostnames from the Route"""
        self.model.spec.hostnames = []

    @modify
    def add_rule(self, backend: "Backend", *route_matches: GRPCRouteMatch):
        """Adds rule to the Route"""
        rules: dict[str, typing.Any] = {"backendRefs": [backend.reference]}
        matches = list(route_matches)
        if matches:
            rules["matches"] = [asdict(match) for match in matches]
        self.model.spec.rules.append(rules)

    @modify
    def remove_all_rules(self):
        """Remove all rules from the Route"""
        self.model.spec.rules = []

    @modify
    def add_backend(self, backend: "Backend", prefix="/"):
        """Adds backend to the Route"""
        if prefix != "/":
            raise ValueError("GRPCRoute does not support path prefix matching")
        self.model.spec.rules.append({"backendRefs": [backend.reference]})

    @modify
    def remove_all_backend(self):
        """Remove all backends from the Route"""
        self.model.spec.rules.clear()

    def wait_for_ready(self):
        """Waits until GRPCRoute is reconciled by known GatewayProvider controllers"""

        expected_controllers = {
            "istio.io/gateway-controller",
            "openshift.io/gateway-controller/v1",
        }

        def _ready(obj):
            for condition_set in obj.model.status.parents:
                if (
                    condition_set.controllerName in expected_controllers
                    or "gateway-controller" in condition_set.controllerName
                ):
                    return all(x.status == "True" for x in condition_set.conditions)
            return False

        success = self.wait_until(_ready, timelimit=10)
        assert success, f"{self.kind()} did not get ready in time"

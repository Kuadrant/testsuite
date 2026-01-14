"""Contains Base class for policies"""

from dataclasses import dataclass
from enum import Enum

from testsuite.kubernetes import KubernetesObject
from testsuite.kuadrant.metrics import get_kuadrant_configs_value, wait_for_policy_applied_to_envoy
from testsuite.utils import check_condition


class EnvoyWaitMixin:
    """Mixin providing Envoy configuration waiting functionality.

    This mixin can be used by any class (Policy, AuthConfig, etc.) that needs to wait
    for Envoy to actually apply WASM configurations after K8s resources are ready.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initial_kuadrant_configs = None
        self._metrics_route = None

    def set_metrics_route(self, metrics_route):
        """Store metrics route for Envoy waiting. Call before commit().

        Args:
            metrics_route: OpenShift Route to gateway metrics service
        """
        self._metrics_route = metrics_route
        if metrics_route is not None:
            self._initial_kuadrant_configs = get_kuadrant_configs_value(metrics_route)

    def wait_for_envoy_applied(self, timeout=120):
        """Wait for configuration to be actually applied in Envoy (WASM config loaded).

        This should be called after wait_for_ready(). Checks that kuadrant_configs
        metric increased, indicating Envoy loaded the new WASM configuration.

        Args:
            timeout: Maximum time to wait in seconds (default: 120)

        Returns:
            True if applied, False if no metrics_route was set
        """
        if self._metrics_route is None:
            # No metrics route configured, skip waiting
            return False

        success = wait_for_policy_applied_to_envoy(self._metrics_route, self._initial_kuadrant_configs, timeout=timeout)
        assert success, (
            f"{self.__class__.__name__} was ready in K8s but did not get applied in Envoy within {timeout}s "
            f"(initial kuadrant_configs: {self._initial_kuadrant_configs})"
        )
        return True


class Strategy(Enum):
    """Class for merge strategies of defaults and overrides."""

    ATOMIC = "atomic"
    MERGE = "merge"


@dataclass
class CelPredicate:
    """Dataclass that references CEL predicate e.g. auth.identity.anonymous == 'true'"""

    predicate: str


@dataclass
class CelExpression:
    """Dataclass that references CEL expression"""

    expression: str


def has_observed_generation(observed_generation):
    """Returns function that asserts whether the object has the expected observedGeneration"""

    def _check(obj):
        return obj.model.status["observedGeneration"] == observed_generation

    return _check


def has_condition(condition_type, status="True", reason=None, message=None):
    """Returns function, that returns True if the Kubernetes object has a specific value"""

    def _check(obj):
        for condition in obj.model.status.conditions:
            if check_condition(condition, condition_type, status, reason, message):
                return True
        return False

    return _check


def is_affected_by(policy: "Policy"):
    """Returns function, that returns True if the Kubernetes object has 'affected by policy' condition"""

    def _check(obj):
        for condition in obj.model.status.conditions:
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

    return _check


class Policy(EnvoyWaitMixin, KubernetesObject):
    """Base class with common functionality for all policies"""

    def wait_for_ready(self):
        """Wait for a Policy to be ready"""
        self.refresh()
        success = self.wait_until(has_observed_generation(self.generation))
        assert success, f"{self.kind()} did not reach observed generation in time"
        self.wait_for_full_enforced()

        # Automatically wait for Envoy application if metrics_route was set
        if self._metrics_route is not None:
            self.wait_for_envoy_applied()

    def wait_for_accepted(self):
        """Wait for a Policy to be Accepted"""
        success = self.wait_until(has_condition("Accepted", "True"))
        assert success, f"{self.kind()} did not get accepted in time"

    def wait_for_partial_enforced(self):
        """Wait for a Policy to be partially Enforced"""
        success = self.wait_until(
            has_condition("Enforced", "True", "Enforced", f"{self.kind(False)} has been partially enforced")
        )
        assert success, f"{self.kind(False)} did not get partially enforced in time"

    def wait_for_full_enforced(self, timelimit=60):
        """Wait for a Policy to be fully Enforced"""
        success = self.wait_until(
            has_condition("Enforced", "True", "Enforced", f"{self.kind(False)} has been successfully enforced"),
            timelimit=timelimit,
        )
        assert success, f"{self.kind()} didn't reach required state, instead it was: {self.model.status.conditions}"

    @property
    def generation(self):
        """Generation property"""
        return self.model.metadata.generation

    @property
    def observed_generation(self):
        """Observed generation property"""
        return self.model.status.observedGeneration

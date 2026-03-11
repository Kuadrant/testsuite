"""
Contains Base class for policies

Metric Validation Mechanism:
----------------------------
Policies track the kuadrant_configs Prometheus metric to verify WASM config propagation to Envoy.

Key Behaviors:
- Each Gateway gets ONE WASM PluginConfiguration (regardless of number of policies)
- First policy on a gateway: metric increases by EXPECTED_METRIC_INCREASE (default: +4)
- Subsequent policies: merged into existing config, metric stays constant (increase: 0)
- Metric persists even after policies are deleted (WASM config remains in Envoy)

Detection Logic:
- Uses metric value as source of truth (if metric > 0, config exists)
- No persistent flags needed - metric itself indicates WASM config presence
- Handles parametrized tests where policies are created/deleted between runs

Assumptions & Limitations:
- Assumes kuadrant_configs metric accurately reflects WASM config count
- Envoy restarts reset metric to 0 (may cause validation failures)
- No cleanup path when gateway is deleted and recreated with same name
- Race conditions possible if policies commit simultaneously (rare in tests)
- Prometheus scrape interval may cause stale metrics (usually negligible)

Usage:
    class MyPolicy(Policy):
        # Override if your policy has different metric behavior
        EXPECTED_METRIC_INCREASE = 4

        def wait_for_ready(self):
            super().wait_for_ready()  # Includes metric validation
"""

from dataclasses import dataclass, is_dataclass
from enum import Enum
import logging

from testsuite.gateway.topology import get_topology
from testsuite.kubernetes import KubernetesObject, modify
from testsuite.utils import check_condition

logger = logging.getLogger(__name__)


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


class Section:
    """
    Generic section handler for policy specs.

    Used for both:
    - Defaults/overrides sections in policies (RateLimitPolicy, AuthPolicy)
    - Nested sections in auth configs (identity, authorization, metadata)

    Provides:
    - Generic section access: get_section()
    - Modify delegation to parent object
    - Generic add_to_spec() helper for dataclass conversion
    - Helper methods: add_item(), clear_all(), strategy()
    """

    def __init__(self, obj, section_name: str = None):
        """
        Initialize section.

        Args:
            obj: Parent object (Policy or AuthConfig)
            section_name: Name of the section (e.g., "defaults", "overrides", "identity")
        """
        self.obj = obj
        self.section_name = section_name

    def get_section(self, subsection: str = None):
        """
        Get the target section from the parent object's spec.

        For policies with defaults/overrides: navigates model.spec[defaults/overrides][subsection]
        For auth nested sections: navigates auth_section[section_name][subsection]

        If subsection is provided, navigates into that nested section.
        """
        # Check if section_name is defaults/overrides (top-level policy sections)
        if self.section_name in ("defaults", "overrides"):
            # Always use model.spec for defaults/overrides
            if hasattr(self.obj, "model"):
                target = self.obj.model.spec.setdefault(self.section_name, {})
            else:
                target = {}
        elif hasattr(self.obj, "auth_section"):
            # For auth nested sections (identity, authorization, metadata)
            if self.section_name:
                target = self.obj.auth_section.setdefault(self.section_name, {})
            else:
                target = self.obj.auth_section
        else:
            # For regular policies, use model.spec
            if self.section_name:
                target = self.obj.model.spec.setdefault(self.section_name, {})
            else:
                target = self.obj.model.spec

        if subsection:
            return target.setdefault(subsection, {})
        return target

    @property
    def committed(self):
        """Delegate to parent object's committed status"""
        return self.obj.committed

    def modify_and_apply(self, modifier_func, retries=2, cmd_args=None):
        """Delegate modify_and_apply to the parent object"""

        def _new_modifier(obj):
            modifier_func(self.__class__(obj, self.section_name))

        return self.obj.modify_and_apply(_new_modifier, retries, cmd_args)

    @modify
    def strategy(self, strategy: Strategy):
        """Add strategy type to this section"""
        target = self.get_section()
        target["strategy"] = strategy.value
        return self

    def add_to_spec(self, spec: dict, **kwargs):
        """
        Generic helper to add any items to a spec dict.

        Automatically converts dataclasses to dicts and handles lists.
        """
        for key, value in kwargs.items():
            if value is None:
                continue
            if isinstance(value, list):
                spec[key] = [asdict(item) if is_dataclass(item) else item for item in value]
            elif is_dataclass(value):
                spec[key] = asdict(value)
            else:
                spec[key] = value

    def add_item(self, name: str, value: dict, **features):
        """Add an item to this section"""
        self.add_to_spec(value, **features)
        self.get_section().update({name: value})

    @modify
    def clear_all(self):
        """Clear content of this section"""
        self.get_section().clear()


class Policy(KubernetesObject):
    """Base class with common functionality for all policies"""

    # Default metric increase for regular policies (AuthPolicy, RateLimitPolicy, etc.)
    # Each policy creates 1 PluginConfiguration in Envoy's WASM shim
    # Empirically, this increases kuadrant_configs metric by 4
    # Note: Multiple policies targeting the same gateway share one WASM config
    EXPECTED_METRIC_INCREASE = 4

    @property
    def _topology(self):
        """Get the global topology registry"""
        from testsuite.gateway.topology import get_topology
        return get_topology()

    def commit(self):
        """
        Commits the policy to the cluster.
        Captures the current kuadrant_configs metric before committing for later validation.

        Assumptions:
        - kuadrant_configs metric increases once per gateway when first policy is created
        - Subsequent policies on the same gateway are merged into existing WASM config (no metric increase)
        - Metric persists even after policies are deleted (WASM config remains in Envoy)
        """
        # Capture initial metric before commit
        if self._topology and hasattr(self.model.spec, 'targetRef'):
            gateway = self._topology.get_gateway_for_target_ref(self.model.spec.targetRef)
            if gateway and hasattr(gateway, 'metrics'):
                try:
                    initial_metric = gateway.metrics.get_kuadrant_configs()
                except Exception as e:  # pylint: disable=broad-except
                    logger.warning(
                        f"Failed to fetch initial metric for policy {self.name()} on gateway "
                        f"{gateway.name()}: {e}. Skipping metric validation."
                    )
                    return super().commit()

                # Use metric as source of truth for WASM config existence
                # If metric > 0, WASM config already exists on this gateway
                # If metric == 0, this is the first policy creating WASM config
                wasm_config_exists = initial_metric > 0
                expected_increase = 0 if wasm_config_exists else self.EXPECTED_METRIC_INCREASE

                logger.debug(
                    f"Policy {self.name()} committing to gateway {gateway.name()}: "
                    f"initial_metric={initial_metric}, wasm_config_exists={wasm_config_exists}, "
                    f"expected_increase={expected_increase}"
                )

                # Store metadata for validation in wait_for_ready()
                self._topology.set_policy_metadata(self, 'initial_kuadrant_configs', initial_metric)
                self._topology.set_policy_metadata(self, 'gateway_name', gateway.name())
                self._topology.set_policy_metadata(self, 'expected_metric_increase', expected_increase)

        return super().commit()

    def _validate_wasm_config_metric(self):
        """
        Validate that kuadrant_configs metric increased by the expected amount.

        For first policy on gateway: expects metric to increase by EXPECTED_METRIC_INCREASE
        For subsequent policies: expects metric to remain unchanged (policies share WASM config)
        """
        if not self._topology:
            logger.warning(
                f"Topology not available for policy {self.name()}, skipping metric validation"
            )
            return

        initial_metric = self._topology.get_policy_metadata(self, 'initial_kuadrant_configs')
        gateway_name = self._topology.get_policy_metadata(self, 'gateway_name')
        expected_increase = self._topology.get_policy_metadata(self, 'expected_metric_increase')

        # If expected_increase not set (backwards compatibility), use class default
        if expected_increase is None:
            logger.debug(
                f"expected_metric_increase not set for policy {self.name()}, "
                f"using class default {self.EXPECTED_METRIC_INCREASE}"
            )
            expected_increase = self.EXPECTED_METRIC_INCREASE

        if initial_metric is not None and gateway_name:
            gateway = self._topology.get_gateway(gateway_name)
            if gateway and hasattr(gateway, 'metrics'):
                expected_metric = initial_metric + expected_increase

                if expected_increase == 0:
                    # Policy shares existing WASM config - metric should NOT change
                    current = gateway.metrics.get_kuadrant_configs()
                    logger.debug(
                        f"Policy {self.name()}: validating metric unchanged "
                        f"(expected={initial_metric}, current={current})"
                    )

                    if current != initial_metric:
                        raise AssertionError(
                            f"kuadrant_configs metric should not have changed for policy {self.name()}. "
                            f"Expected: {initial_metric}, Actual: {current}. "
                            f"This policy should be merged into existing WASM config."
                        )
                else:
                    # First policy on gateway - metric should increase
                    logger.debug(
                        f"Policy {self.name()}: waiting for metric to reach {expected_metric} "
                        f"(initial={initial_metric} + increase={expected_increase})"
                    )
                    gateway.metrics.wait_for_kuadrant_config_value(expected_metric)

                    final_metric = gateway.metrics.get_kuadrant_configs()
                    logger.debug(
                        f"Policy {self.name()}: metric validation successful (final={final_metric})"
                    )

    def wait_for_ready(self):
        """
        Wait for a Policy to be ready.
        Verifies observedGeneration, Enforced status, and kuadrant_configs metric.
        """
        self.refresh()
        success = self.wait_until(has_observed_generation(self.generation))
        assert success, f"{self.kind()} did not reach observed generation in time"
        self.wait_for_full_enforced()
        self._validate_wasm_config_metric()

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

"""Contains Base class for policies"""

from dataclasses import dataclass, is_dataclass
from enum import Enum

from testsuite.gateway.topology import get_topology
from testsuite.kubernetes import KubernetesObject, modify
from testsuite.utils import check_condition


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

    @property
    def _topology(self):
        """Get the global topology registry"""
        from testsuite.gateway.topology import get_topology
        return get_topology()

    def commit(self):
        """
        Commits the policy to the cluster.
        Captures the current kuadrant_configs metric before committing for later validation.
        """
        # Capture initial metric before commit
        if self._topology and hasattr(self.model.spec, 'targetRef'):
            target_ref = self.model.spec.targetRef
            gateway = self._topology.get_gateway_for_target_ref(target_ref)
            if gateway and hasattr(gateway, 'metrics'):
                try:
                    initial_metric = gateway.metrics.get_kuadrant_configs()
                except Exception:  # pylint: disable=broad-except
                    initial_metric = 0

                # Determine if WasmPlugin config will change based on:
                # 1. Topology: are there other policies for this target?
                # 2. Gateway flag: has WasmPlugin ever been created for this gateway?
                target_kind = target_ref.kind
                target_name = target_ref.name

                # Check topology for existing policies
                if target_kind == "HTTPRoute":
                    existing_policies = self._topology.get_policies_for_route(target_name)
                elif target_kind == "Gateway":
                    existing_policies = self._topology.get_policies_for_gateway(target_name)
                else:
                    existing_policies = []

                # Filter out current policy if already registered
                existing_policies = [p for p in existing_policies if p.name() != self.name()]

                # Check gateway metadata flag for WasmPlugin creation
                gateway_node = self._topology.get_node(gateway.name())
                wasm_config_ever_created = gateway_node and gateway_node.metadata.get('wasm_config_created', False)

                # Expect metric increase if: no existing policies AND no WasmPlugin created yet
                expect_metric_increase = len(existing_policies) == 0 and not wasm_config_ever_created

                # Mark that WasmPlugin will be created for this gateway
                if gateway_node and expect_metric_increase:
                    gateway_node.metadata['wasm_config_created'] = True

                # Store metadata for validation in wait_for_ready()
                self._topology.set_policy_metadata(self, 'initial_kuadrant_configs', initial_metric)
                self._topology.set_policy_metadata(self, 'expect_metric_increase', expect_metric_increase)
                self._topology.set_policy_metadata(self, 'gateway_name', gateway.name())

        return super().commit()

    def _validate_wasm_config_metric(self):
        """Validate that the kuadrant_configs metric changed as expected after policy commit"""
        if not self._topology:
            return

        initial_metric = self._topology.get_policy_metadata(self, 'initial_kuadrant_configs')
        gateway_name = self._topology.get_policy_metadata(self, 'gateway_name')
        expect_metric_increase = self._topology.get_policy_metadata(self, 'expect_metric_increase')

        if initial_metric is None or gateway_name is None:
            return

        gateway = self._topology.get_gateway(gateway_name)
        if not gateway or not hasattr(gateway, 'metrics'):
            return

        # Wait for metric to reach expected state
        if expect_metric_increase:
            # First policy for this target - metric should increase
            gateway.metrics.wait_for_kuadrant_config_increase(initial_metric)
        else:
            # Policy updates existing WasmPlugin - metric should stay same
            # Just verify it didn't decrease
            current_metric = gateway.metrics.get_kuadrant_configs()
            if current_metric < initial_metric:
                raise AssertionError(
                    f"kuadrant_configs metric decreased unexpectedly for policy {self.name()}. "
                    f"Initial: {initial_metric}, Current: {current_metric}"
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

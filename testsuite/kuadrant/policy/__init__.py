"""Contains Base class for policies"""

from dataclasses import dataclass, is_dataclass
from enum import Enum

from testsuite.core.topology import get_topology
from testsuite.kubernetes import KubernetesObject, modify
from testsuite.kuadrant.policy.metric_validator import WasmMetricValidator
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
        from testsuite.core.topology import get_topology
        return get_topology()

    def commit(self):
        """Commits the policy to the cluster."""
        WasmMetricValidator.prepare_validation(self, self._topology)
        return super().commit()

    def wait_for_ready(self):
        """
        Wait for a Policy to be ready.
        Verifies observedGeneration, Enforced status, and kuadrant_configs metric.
        """
        self.refresh()
        success = self.wait_until(has_observed_generation(self.generation))
        assert success, f"{self.kind()} did not reach observed generation in time"
        self.wait_for_full_enforced()
        WasmMetricValidator.validate_metrics(self, self._topology)

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

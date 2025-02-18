"""Contains Base class for policies"""

from dataclasses import dataclass
from enum import Enum

from testsuite.kubernetes import KubernetesObject
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


class Policy(KubernetesObject):
    """Base class with common functionality for all policies"""

    def wait_for_ready(self):
        """Wait for a Policy to be ready"""
        self.wait_for_full_enforced()

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
        assert success, f"{self.kind()} did not get fully enforced in time"

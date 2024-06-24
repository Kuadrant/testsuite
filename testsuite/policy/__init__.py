"""Contains Base class for policies"""

from testsuite.openshift import OpenShiftObject
from testsuite.utils import check_condition


def has_condition(condition_type, status="True", reason=None, message=None):
    """Returns function, that returns True if the Kubernetes object has a specific value"""

    def _check(obj):
        for condition in obj.model.status.conditions:
            if check_condition(condition, condition_type, status, reason, message):
                return True
        return False

    return _check


class Policy(OpenShiftObject):
    """Base class with common functionality for all policies"""

    def wait_for_ready(self, timelimit=60):
        """Wait for a Policy to be Enforced"""
        success = self.wait_until(has_condition("Enforced", "True"), timelimit=timelimit)
        assert success, f"{self.kind()} did not get ready in time"

    def wait_for_accepted(self):
        """Wait for a Policy to be Accepted"""
        success = self.wait_until(has_condition("Accepted", "True"))
        assert success, f"{self.kind()} did not get accepted in time"

"""Contains Base class for policies"""

from testsuite.openshift import OpenShiftObject
from testsuite.utils import has_condition


class Policy(OpenShiftObject):
    """Base class with common functionality for all policies"""

    def wait_for_ready(self):
        """Wait for a Policy to be Enforced"""
        success = self.wait_until(has_condition("Enforced", "True"))
        assert success, f"{self.kind()} did not get ready in time"

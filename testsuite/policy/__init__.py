"""Contains Base class for policies"""

import openshift_client as oc

from testsuite.openshift import OpenShiftObject
from testsuite.utils import has_condition


class Policy(OpenShiftObject):
    """Base class with common functionality for all policies"""

    def wait_for_ready(self):
        """Wait for a Policy to be Enforced"""
        with oc.timeout(90):
            success, _, _ = self.self_selector().until_all(
                success_func=has_condition("Enforced", "True"),
                tolerate_failures=5,
            )
            assert success, f"{self.kind()} did not get ready in time"

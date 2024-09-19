"""Test not supported geocode in geo load-balancing"""

import pytest

from testsuite.kuadrant.policy import has_condition

pytestmark = [pytest.mark.multicluster]


def test_unsupported_geocode(dns_policy):
    """Change default geocode to not existent one and verify that policy became not enforced"""
    dns_policy.model.spec.loadBalancing.geo = "XX"
    dns_policy.apply()

    assert dns_policy.wait_until(has_condition("Enforced", "False"))

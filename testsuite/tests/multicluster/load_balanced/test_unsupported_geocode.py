"""Test not supported geocode in geo load-balancing"""

import pytest

from testsuite.kuadrant.policy import has_condition
from testsuite.kuadrant.policy.dns import has_record_condition

pytestmark = [pytest.mark.multicluster]


def test_unsupported_geocode(dns_policy):
    """Change default geocode to not existent one and verify that policy became not enforced"""
    dns_policy.model.spec.loadBalancing.geo = "XX"
    dns_policy.apply()

    assert dns_policy.wait_until(has_condition("Enforced", "False"))
    assert dns_policy.wait_until(
        has_record_condition("Ready", "False", "ProviderError", "Cannot find location")
    ), f"DNSPolicy did not reach expected record status, instead it was: {dns_policy.model.status.recordConditions}"

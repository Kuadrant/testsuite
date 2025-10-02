"""Test DNSPolicy behavior with no default DNS provider secret available"""

import pytest

from testsuite.kuadrant.policy import has_condition
from testsuite.kuadrant.policy.dns import DNSPolicy, has_record_condition

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy, pytest.mark.disruptive]


@pytest.fixture(scope="module")
def dns_policy(blame, gateway, module_label):
    """Return DNSPolicy without proivderRefs configured"""
    return DNSPolicy.create_instance(gateway.cluster, blame("dns"), gateway, labels={"app": module_label})


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, dns_policy):  # pylint: disable=unused-argument
    """Commits all important stuff before tests"""
    request.addfinalizer(dns_policy.delete)
    dns_policy.commit()


def test_no_default_provider_secrets(dns_policy):
    """Test that DNSPolicy and DNSRecord both end up in error state, when no default provider secret exists"""
    assert dns_policy.wait_until(
        has_condition("Enforced", "False", "Unknown", "not a single DNSRecord is ready")
    ), f"DNSPolicy did not reach expected status, instead it was: {dns_policy.model.status.conditions}"
    assert dns_policy.wait_until(
        has_record_condition(
            "Ready",
            "False",
            "DNSProviderError",
            "No default provider secret labeled kuadrant.io/default-provider was found",
        )
    ), f"DNSPolicy's DNSRecord didn't reach expected status, instead it was: {dns_policy.model.status.conditions}"

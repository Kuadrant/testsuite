"""Test DNSPolicy behavior with a non-existing DNS provider secret"""

import pytest

from testsuite.kuadrant.policy import has_condition
from testsuite.kuadrant.policy.dns import has_record_condition
from testsuite.kuadrant.policy.dns import DNSPolicy

pytestmark = [pytest.mark.dnspolicy]

NON_EXISTING_SECRET = "should-not-exist"


@pytest.fixture(scope="module")
def dns_policy(blame, gateway, module_label):
    """Returns DNSPolicy fixture referencing a non-existing secret"""
    return DNSPolicy.create_instance(
        gateway.cluster, blame("dns"), gateway, NON_EXISTING_SECRET, labels={"app": module_label}
    )


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, dns_policy):  # pylint: disable=unused-argument
    """Commits all important stuff before tests"""
    request.addfinalizer(dns_policy.delete)
    dns_policy.commit()


def test_default_secret_provider_not_found(dns_policy):
    """Assert DNSPolicy and DNSRecord both end up in error state, with DNS provider secret does not exist message"""
    assert dns_policy.wait_until(
        has_condition("Enforced", "False", "Unknown", "not a single DNSRecord is ready")
    ), f"DNSPolicy did not reach expected status, instead it was: {dns_policy.model.status.conditions}"
    assert dns_policy.wait_until(
        has_record_condition(
            "Ready",
            "False",
            "DNSProviderError",
            f'The dns provider could not be loaded: Secret "{NON_EXISTING_SECRET}" not found',
        )
    ), f"DNSPolicy did not reach expected record status, instead it was: {dns_policy.model.status.recordConditions}"

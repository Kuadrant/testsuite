"""Test what happens when 2 default DNS provider secrets exist at the same time"""

import pytest

import openshift_client as oc

from testsuite.kubernetes.secret import Secret
from testsuite.kuadrant.policy import has_condition
from testsuite.kuadrant.policy.dns import DNSPolicy, has_record_condition

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy, pytest.mark.disruptive]


@pytest.fixture(scope="module")
def default_provider_secrets(request, dns_provider_secret, cluster, blame, module_label):
    """Create two default DNS provider secrets from existing, non-default provider"""
    provider_secret = oc.selector(f"secret/{dns_provider_secret}", static_context=cluster.context).object(cls=Secret)
    for _ in range(2):
        default_secret = Secret.create_instance(
            cluster,
            blame("dflt-dns"),
            data=provider_secret.model.data,
            secret_type=provider_secret.model.type,
            labels={"kuadrant.io/default-provider": "true", "app": module_label},
        )
        request.addfinalizer(default_secret.delete)
        default_secret.commit()


@pytest.fixture(scope="module")
def dns_policy(blame, gateway, module_label):
    """Return DNSPolicy with delegate true and providerRefs secret"""
    return DNSPolicy.create_instance(gateway.cluster, blame("dns"), gateway, labels={"app": module_label})


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, default_provider_secrets, dns_policy):  # pylint: disable=unused-argument
    """Commits all important stuff before tests"""
    request.addfinalizer(dns_policy.delete)
    dns_policy.commit()


def test_multiple_default_provider_secrets(dns_policy):
    """Check that authoritative DNSRecord ends up in error state when multiple default provider secrets exist"""
    assert dns_policy.wait_until(
        has_condition("Enforced", "False", "Unknown", "not a single DNSRecord is ready")
    ), f"DNSPolicy did not reach expected status, instead it was: {dns_policy.model.status.conditions}"
    assert dns_policy.wait_until(
        has_record_condition(
            "Ready", "False", "DNSProviderError", "Multiple default providers secrets found. Only one expected"
        )
    ), f"Authoritative DNSRecord didn't reach expected status, instead it was: {dns_policy.model.status.conditions}"

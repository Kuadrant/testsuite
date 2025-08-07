"""
Tests that a DNSPolicy targeting a specific `sectionName` of a Gateway
only creates a DNS record for that section's hostname.
This test verifies that a DNSPolicy targeting a specific sectionName of a Gateway:
- Becomes enforced successfully.
- Reports exactly one DNS record created (totalRecords == 1).
- Allows requests to the managed domain to succeed (returns HTTP 200).
- Fails to resolve the unmanaged domain (DNS resolution fails).
"""

import pytest


from testsuite.gateway import CustomReference, GatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.httpx import KuadrantClient
from testsuite.kuadrant.policy.dns import DNSPolicy


pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy]


MANAGED_LISTENER_NAME = "managed-listener"
UNMANAGED_LISTENER_NAME = "unmanaged-listener"


@pytest.fixture(scope="module")
def authorization():
    """Disables the default creation of an AuthPolicy"""
    return None


@pytest.fixture(scope="module")
def client(authorization):
    """Returns a KuadrantClient configured for this test module."""
    return KuadrantClient(auth=authorization, verify=False)


@pytest.fixture(scope="module")
def managed_domain(base_domain):
    """Returns the hostname assigned to the managed listener (DNS policy will target this)"""
    return f"managed.{base_domain}"


@pytest.fixture(scope="module")
def unmanaged_domain(base_domain):
    """Returns the hostname assigned to the unmanaged listener (DNS policy will not affect this)"""
    return f"unmanaged.{base_domain}"


@pytest.fixture(scope="module")
def gateway(gateway: KuadrantGateway, managed_domain, unmanaged_domain):
    """
    Modifies the existing, shared gateway for the purposes of this test module.
    It adds two specific HTTP listeners (one for the managed and one for the
    unmanaged domain). After the tests in this module complete, these listeners
    are removed to restore the gateway to its original state.
    """

    gateway.add_listener(GatewayListener(name=MANAGED_LISTENER_NAME, hostname=managed_domain))
    gateway.add_listener(GatewayListener(name=UNMANAGED_LISTENER_NAME, hostname=unmanaged_domain))

    gateway.wait_for_ready()

    yield gateway

    gateway.remove_listener(MANAGED_LISTENER_NAME)
    gateway.remove_listener(UNMANAGED_LISTENER_NAME)

    gateway.wait_for_ready()


@pytest.fixture(scope="module")
def route(route: HTTPRoute, managed_domain, unmanaged_domain, _hostname):
    """
    Temporarily replaces the hostnames on the existing HTTPRoute
    for the duration of the test module.
    """
    original_hostnames = list(route.hostnames)
    route.remove_all_hostnames()
    route.add_hostname(managed_domain)
    route.add_hostname(unmanaged_domain)
    route.wait_for_ready()

    yield route

    route.remove_all_hostnames()
    for original_hostname in original_hostnames:
        route.add_hostname(original_hostname)
    route.wait_for_ready()


@pytest.fixture(scope="module")
def dns_policy(request, gateway, blame, module_label, dns_provider_secret):
    """
    Creates a DNSPolicy targeting only the managed listener using sectionName.
    This ensures the policy is scoped to that specific part of the Gateway.
    """
    parent_ref = CustomReference(sectionName=MANAGED_LISTENER_NAME, **gateway.reference)
    policy = DNSPolicy.create_instance(
        cluster=gateway.cluster,
        name=blame("dns-section"),
        parent=parent_ref,
        provider_secret_name=dns_provider_secret,
        labels={"testRun": module_label},
    )
    request.addfinalizer(policy.delete)
    return policy


@pytest.mark.usefixtures("route")
def test_dns_policy_section_name_targeting_gateway_listener(dns_policy, managed_domain, unmanaged_domain, client):
    """
    Tests that a DNSPolicy with a specific `sectionName` creates a DNS record
    only for the targeted Gateway listener's hostname.
    The Gateway has two listeners (managed and unmanaged); the policy targets
    only the managed one. The test verifies that:
    - The policy is enforced and exactly one DNS record is created.
    - The managed domain resolves and returns 200.
    - The unmanaged domain fails DNS resolution.
    """
    # Wait until exactly one DNS record is present
    assert dns_policy.wait_until(
        lambda policy: policy.model.status.get("totalRecords", 0) == 1
    ), "Timed out waiting for DNSPolicy to report totalRecords == 1"

    # Verify the managed domain is accessible.
    response_managed = client.get(f"http://{managed_domain}/get")
    assert response_managed.status_code == 200, "Managed domain should be accessible"

    # Verify the unmanaged domain does not resolve.
    response_unmanaged = client.get(f"http://{unmanaged_domain}/get")
    assert response_unmanaged.has_dns_error(), "Unmanaged domain should have a DNS resolution error"

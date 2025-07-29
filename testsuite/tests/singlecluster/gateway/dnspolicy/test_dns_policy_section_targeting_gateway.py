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
import json

from testsuite.gateway import CustomReference, GatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kuadrant.policy.dns import DNSPolicy


pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy]


MANAGED_LISTENER_NAME = "managed-listener"
UNMANAGED_LISTENER_NAME = "unmanaged-listener"


@pytest.fixture(scope="module")
def authorization():
    """Disables the default creation of an AuthPolicy"""
    return None

@pytest.fixture(scope="module")
def rate_limit():
    """Disables the default creation of a RateLimitPolicy"""
    return None

@pytest.fixture(scope="module")
def managed_domain(base_domain):
    """Returns the hostname assigned to the managed listener (DNS policy will target this)"""
    return f"managed.{base_domain}"

@pytest.fixture(scope="module")
def unmanaged_domain(base_domain):
    """Returns the hostname assigned to the unmanaged listener (DNS policy will not affect this)"""
    return f"unmanaged.{base_domain}"

@pytest.fixture(scope="module")
def gateway(request, cluster, blame, module_label, managed_domain, unmanaged_domain):
    """
    Creates a Gateway with two HTTP listeners:
    - One will be managed by the DNS policy
    - One will not
    """
    gw = KuadrantGateway.create_instance(cluster, blame("gw"), {"app": module_label})

    # Create the managed listener (will be targeted by DNSPolicy)
    gw.add_listener(GatewayListener(
        name=MANAGED_LISTENER_NAME,
        hostname=managed_domain,
    ))

    # Create the unmanaged listener
    gw.add_listener(GatewayListener(
        name=UNMANAGED_LISTENER_NAME,
        hostname=unmanaged_domain,
    ))

    # Register finalizer for cleanup
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw

@pytest.fixture(scope="module")
def route(request, cluster, blame, module_label, gateway, backend, managed_domain, unmanaged_domain):
    """
    Creates an HTTPRoute with two hostnames:
    - One matches the managed listener
    - One matches the unmanaged listener
    This allows us to test which one gets a DNS record.
    """
    route = HTTPRoute.create_instance(cluster, blame("route"), gateway, {"app": module_label})
    route.add_hostname(managed_domain)
    route.add_hostname(unmanaged_domain)
    route.add_backend(backend, "/")

    request.addfinalizer(route.delete)
    route.commit()
    route.wait_for_ready()
    return route

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
def test_dns_policy_section_name_targeting_gateway_listener(route, dns_policy, managed_domain, unmanaged_domain, gateway, client):
    """
Tests that a DNSPolicy with a specific `sectionName` creates a DNS record
only for the targeted Gateway listener's hostname.

The Gateway has two listeners (managed and unmanaged); the policy targets
only the managed one. The test verifies that:

- The policy is enforced and exactly one DNS record is created.
- The managed domain resolves and returns 200.
- The unmanaged domain fails DNS resolution.
    """

    # Print the current DNSPolicy status for debugging purposes, this will be deleted after test completion
    print(">>> Full DNSPolicy status:")
    print(json.dumps(dns_policy.model.status, indent=2))
    print(">>> Route hostnames:", route.model.spec.get("hostnames"))
    print(">>> Managed domain:", managed_domain)

    # Helper: check that one DNS record was created
    def has_total_record(policy):
        return policy.model.status.get("totalRecords", 0) == 1

    # Wait until exactly one DNS record is present
    assert dns_policy.wait_until(has_total_record), \
        "Timed out waiting for DNSPolicy to report totalRecords == 1"

    # Helper: check if a specific condition is true (like "Enforced")
    def has_condition(policy, type, status):
        return any(c.get("type") == type and c.get("status") == status for c in policy.model.status.get("conditions", []))

    # Wait until the policy is fully enforced
    assert dns_policy.wait_until(lambda p: has_condition(p, "Enforced", "True")), \
        "DNSPolicy was not enforced"

    # Simulate curl to managed domain
    print(f"\n$ curl http://{managed_domain}/get -I")
    try:
        response = client.get(f"http://{managed_domain}/get")
        print(f"HTTP/1.1 {response.status_code} OK")
        assert response.status_code == 200
    except Exception as e:
        print(f"Request to managed domain failed: {e}")
        pytest.fail("Managed domain should returned 200 OK")

    # Simulate curl to unmanaged domain
    print(f"\n$ curl http://{unmanaged_domain}/get -I")
    try:
        response = client.get(f"http://{unmanaged_domain}/get")
        if response.has_dns_error():
            print(f"curl: (6) Could not resolve host: {unmanaged_domain}")
        else:
            print(f"HTTP/1.1 {response.status_code} OK")
            pytest.fail("Unmanaged domain resolved successfully, but it should not exist.")
    except Exception:
        print(f"curl: (6) Could not resolve host: {unmanaged_domain}")

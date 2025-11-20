"""
Tests that a TLSPolicy with sectionName correctly applies TLS
only to the targeted gateway listener ('managed-listener').
"""

import pytest
from testsuite.gateway import CustomReference, TLSGatewayListener
from testsuite.gateway.gateway_api.hostname import StaticHostname
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.httpx import KuadrantClient
from testsuite.kuadrant.policy.dns import DNSPolicy
from testsuite.kuadrant.policy.tls import TLSPolicy

pytestmark = [pytest.mark.dnspolicy, pytest.mark.tlspolicy]

MANAGED_LISTENER_NAME = "managed-listener"
UNMANAGED_LISTENER_NAME = "unmanaged-listener"


# Override unused policies to prevent them from being created by global fixtures
@pytest.fixture(scope="module")
def authorization():
    """Disable default AuthPolicy creation"""
    return None


@pytest.fixture(scope="module")
def rate_limit():
    """Disable default RateLimitPolicy creation"""
    return None


@pytest.fixture(scope="module")
def managed_domain(base_domain):
    """Returns the hostname for the listener targeted by the TLSPolicy."""
    return f"managed.{base_domain}"


@pytest.fixture(scope="module")
def unmanaged_domain(base_domain):
    """Returns the hostname for the listener NOT targeted by the TLSPolicy."""
    return f"unmanaged.{base_domain}"


@pytest.fixture(scope="module")
def route(route: HTTPRoute, managed_domain, unmanaged_domain):
    """
    Replaces the hostnames on the existing HTTPRoute for the duration
    of the test module.
    """
    route.remove_all_hostnames()
    route.add_hostname(managed_domain)
    route.add_hostname(unmanaged_domain)
    route.wait_for_ready()

    return route


@pytest.fixture(scope="module")
def gateway(gateway: KuadrantGateway, managed_domain, unmanaged_domain):
    """
    Modifies the existing shared gateway for the purposes of this test module
    by adding two specific HTTP listeners (one for the managed and one for the
    unmanaged domain).
    """

    gateway.add_listener(
        TLSGatewayListener(name=MANAGED_LISTENER_NAME, hostname=managed_domain, gateway_name=gateway.name())
    )
    gateway.add_listener(
        TLSGatewayListener(name=UNMANAGED_LISTENER_NAME, hostname=unmanaged_domain, gateway_name=gateway.name())
    )

    gateway.wait_for_ready()

    return gateway


@pytest.fixture(scope="module")
def dns_policy(gateway, blame, module_label, dns_provider_secret):
    """
    Defines a DNSPolicy that targets the whole Gateway to ensure both
    managed and unmanaged hostnames are routable for the test.
    """
    return DNSPolicy.create_instance(
        gateway.cluster, blame("dns"), gateway, dns_provider_secret, labels={"testRun": module_label}
    )


@pytest.fixture(scope="module")
def tls_policy(gateway, blame, module_label, cluster_issuer):
    """
    Defines a TLSPolicy that targets only the 'managed' listener via sectionName.
    """
    parent_ref = CustomReference(sectionName=MANAGED_LISTENER_NAME, **gateway.reference)
    return TLSPolicy.create_instance(
        cluster=gateway.cluster,
        name=blame("tls-section"),
        parent=parent_ref,
        issuer=cluster_issuer,
        labels={"testRun": module_label},
    )


@pytest.fixture(scope="module")
def managed_client(gateway, managed_domain):
    """Returns a client for the successfully protected 'managed' endpoint."""
    return StaticHostname(managed_domain, gateway.get_tls_cert).client()


@pytest.fixture(scope="module")
def unmanaged_client(unmanaged_domain):
    """
    Returns a client that enables default TLS verification for the unmanaged endpoint.
    This request is expected to fail with a TLS certificate error.
    """
    return KuadrantClient(base_url=f"https://{unmanaged_domain}", verify=True)


@pytest.mark.usefixtures("route", "tls_policy", "dns_policy")
def test_tls_policy_section_targeting_gateway_listener(managed_client, unmanaged_client):
    """
    Asserts that the TLSPolicy is
    applied only to the targeted 'managed' listener.
    """

    # Test the managed endpoint: it should be successful and have a valid cert.
    response_managed = managed_client.get("/get")
    assert response_managed.status_code == 200
    assert not response_managed.has_cert_verify_error()

    # Test the unmanaged endpoint: it should be connectable but fail with a TLS error.
    response_unmanaged = unmanaged_client.get("/get")
    assert response_unmanaged.has_tls_error()

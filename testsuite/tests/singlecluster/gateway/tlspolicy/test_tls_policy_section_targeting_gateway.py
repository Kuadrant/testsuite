"""
Tests that a TLSPolicy with sectionName correctly applies TLS
only to the targeted gateway listener ('api').
"""

import pytest
from testsuite.gateway import CustomReference, TLSGatewayListener
from testsuite.gateway.gateway_api.hostname import StaticHostname
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.httpx import KuadrantClient
from testsuite.kuadrant.policy.dns import DNSPolicy
from testsuite.kuadrant.policy.tls import TLSPolicy

pytestmark = [pytest.mark.kuadrant_only]

API_LISTENER_NAME = "api"


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
def api_hostname(base_domain):
    """Returns the hostname for the targeted listener."""
    return f"api.{base_domain}"


@pytest.fixture(scope="module")
def extra_hostname(base_domain):
    """Returns the hostname for the non-targeted listener."""
    return f"extra.{base_domain}"


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, module_label, api_hostname, extra_hostname):
    """Gateway with two named TLS listeners for explicit targeting."""
    gw = KuadrantGateway.create_instance(cluster, blame("gw"), {"testRun": module_label})
    gw.add_listener(TLSGatewayListener(name=API_LISTENER_NAME, hostname=api_hostname, gateway_name=gw.name()))
    gw.add_listener(TLSGatewayListener(name="extra", hostname=extra_hostname, gateway_name=gw.name()))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def route(request, cluster, blame, module_label, gateway, backend, api_hostname, extra_hostname):
    """Creates a single HTTPRoute with two hostnames, attaching to both gateway listeners."""
    route = HTTPRoute.create_instance(cluster, blame("route"), gateway, {"app": module_label})
    route.add_hostname(api_hostname)
    route.add_hostname(extra_hostname)
    route.add_backend(backend, "/")
    request.addfinalizer(route.delete)
    route.commit()
    return route


@pytest.fixture(scope="module")
def dns_policy(gateway, blame, module_label, dns_provider_secret):
    """Defines a DNSPolicy object."""
    return DNSPolicy.create_instance(
        gateway.cluster, blame("dns"), gateway, dns_provider_secret, labels={"testRun": module_label}
    )


@pytest.fixture(scope="module")
def tls_policy(gateway, blame, module_label, cluster_issuer):
    """Defines a TLSPolicy object using a simplified reference."""
    # Unpack the gateway's reference and add the sectionName
    parent_ref = CustomReference(sectionName=API_LISTENER_NAME, **gateway.reference)
    return TLSPolicy.create_instance(
        cluster=gateway.cluster,
        name=blame("tls-section"),
        parent=parent_ref,
        issuer=cluster_issuer,
        labels={"testRun": module_label},
    )


@pytest.fixture(scope="module")
def api_client(gateway, api_hostname):
    """Returns a client for the successfully protected 'api' endpoint."""
    return StaticHostname(api_hostname, gateway.get_tls_cert).client()


@pytest.fixture(scope="module")
def extra_client(extra_hostname):
    """
    Returns a client that enables default TLS verification, which is expected
    to fail and be caught internally by the KuadrantClient.
    """
    return KuadrantClient(base_url=f"https://{extra_hostname}", verify=True)


@pytest.mark.usefixtures("route")
def test_tls_policy_section_targeting_gateway_listener(tls_policy, dns_policy, api_client, extra_client):
    """
    Waits for policies to be ready, then asserts that the TLSPolicy is
    applied only to the targeted 'api' listener.
    """
    # Wait for the prerequisite policies to be ready.
    dns_policy.wait_for_ready()
    tls_policy.wait_for_ready()

    # Test the targeted endpoint: it should be successful and have a valid cert
    response_api = api_client.get("/get")
    assert response_api.status_code == 200
    assert not response_api.has_cert_verify_error()

    # Test the non-targeted endpoint: it should fail with a TLS error
    response_extra = extra_client.get("/get")
    assert response_extra.has_tls_error()

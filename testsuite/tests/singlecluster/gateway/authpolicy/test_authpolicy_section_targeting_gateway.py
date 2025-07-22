"""
Tests that an AuthPolicy is correctly applied to a specific listener section of
a Gateway, protecting only the traffic handled by that named listener.
It verifies that the targeted listener is protected by the policy, while the
other listener on the same Gateway remains public and unaffected.
"""

import pytest
from testsuite.gateway import TLSGatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.hostname import StaticHostname
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kuadrant.policy.dns import DNSPolicy
from testsuite.kuadrant.policy.tls import TLSPolicy


pytestmark = [pytest.mark.kuadrant_only]

SECURE_LISTENER_NAME = "secure-listener"
PUBLIC_LISTENER_NAME = "public-listener"


@pytest.fixture(scope="module")
def secure_domain(base_domain):
    """Returns the hostname for the secure, targeted listener."""
    return f"secure.{base_domain}"


@pytest.fixture(scope="module")
def public_domain(base_domain):
    """Returns the hostname for the public, non-targeted listener."""
    return f"public.{base_domain}"


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, module_label, secure_domain, public_domain):
    """
    Creates a single Gateway resource with two separate listeners.
    Core setup needed to test that a policy can target one listener while
    ignoring the other.
    """
    gw = KuadrantGateway.create_instance(cluster, blame("gw"), {"app": module_label})
    gw.add_listener(
        TLSGatewayListener(
            hostname=secure_domain,
            gateway_name=gw.name(),
            name=SECURE_LISTENER_NAME,
        )
    )
    gw.add_listener(
        TLSGatewayListener(
            hostname=public_domain,
            gateway_name=gw.name(),
            name=PUBLIC_LISTENER_NAME,
        )
    )
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def custom_client(gateway):
    """
    While changing TLS listeners the TLS certificate changes so a new client needs to be generated
    to fetch newest tls cert from cluster.
    """

    def _client_new(hostname: str):
        return StaticHostname(hostname, gateway.get_tls_cert).client()

    return _client_new


@pytest.fixture(scope="module")
def secure_route(request, cluster, blame, module_label, gateway, backend, secure_domain):
    """Creates an HTTPRoute specifically for the secure domain."""
    route = HTTPRoute.create_instance(cluster, blame("secure-route"), gateway, {"app": module_label})
    route.add_hostname(secure_domain)
    route.add_backend(backend, "/")
    request.addfinalizer(route.delete)
    route.commit()
    return route


@pytest.fixture(scope="module")
def public_route(request, cluster, blame, module_label, gateway, backend, public_domain):
    """Creates an HTTPRoute specifically for the public domain."""
    route = HTTPRoute.create_instance(cluster, blame("public-route"), gateway, {"app": module_label})
    route.add_hostname(public_domain)
    route.add_backend(backend, "/")
    request.addfinalizer(route.delete)
    route.commit()
    return route


@pytest.fixture(scope="module")
def tls_policy(blame, gateway, module_label, cluster_issuer):
    """Creates a TLSPolicy that will cover all listeners on the Gateway."""
    policy = TLSPolicy.create_instance(
        gateway.cluster, blame("tls"), parent=gateway, issuer=cluster_issuer, labels={"app": module_label}
    )
    return policy


@pytest.fixture(scope="module")
def dns_policy(blame, gateway, module_label, dns_provider_secret):
    """Creates a DNSPolicy that will cover all listeners on the Gateway."""
    policy = DNSPolicy.create_instance(
        gateway.cluster, blame("dns"), gateway, dns_provider_secret, labels={"app": module_label}
    )
    return policy


@pytest.fixture(scope="module")
def authorization(
    cluster, blame, module_label, oidc_provider, gateway, public_route, secure_route
):  # pylint: disable=unused-argument
    """Creates an AuthPolicy that targets ONLY the 'secure-listener' section."""
    policy = AuthPolicy.create_instance(
        cluster,
        blame("authz"),
        gateway,
        section_name=SECURE_LISTENER_NAME,
        labels={"testRun": module_label},
    )
    policy.identity.add_oidc("oidc-auth", oidc_provider.well_known["issuer"])
    return policy


@pytest.mark.usefixtures("authorization", "secure_route", "public_route")
def test_gateway_listener_section_targeting(custom_client, auth, secure_domain, public_domain):
    """
    Tests that an AuthPolicy attached to a specific Gateway listener protects
    only the traffic handled by that listener.
    """
    public_client = custom_client(public_domain)
    response = public_client.get("/get")
    assert response.status_code == 200, "The public listener should not require auth"

    secure_client = custom_client(secure_domain)
    response = secure_client.get("/get")
    assert response.status_code == 401, "The secure listener should require auth"

    response = secure_client.get("/get", auth=auth)
    assert response.status_code == 200, "The secure listener should allow requests with valid auth"

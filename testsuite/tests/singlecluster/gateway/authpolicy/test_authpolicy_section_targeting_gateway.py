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
def gateway(gateway: KuadrantGateway, secure_domain, public_domain):
    """
    Modifies the existing, shared gateway for this test module.
    It adds two specific TLS listeners and applies the changes.
    Core setup needed to test that a policy can target one listener while
    ignoring the other. After the test in this module complete, these listeners
    are removed to restore the gateway to its original state.
    """
    gateway.add_listener(
        TLSGatewayListener(
            hostname=secure_domain,
            gateway_name=gateway.name(),
            name=SECURE_LISTENER_NAME,
        )
    )
    gateway.add_listener(
        TLSGatewayListener(
            hostname=public_domain,
            gateway_name=gateway.name(),
            name=PUBLIC_LISTENER_NAME,
        )
    )

    gateway.wait_for_ready()

    yield gateway

    gateway.remove_listener(SECURE_LISTENER_NAME)
    gateway.remove_listener(PUBLIC_LISTENER_NAME)

    gateway.wait_for_ready()


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


def test_authpolicy_section_name_targeting_gateway_listener(custom_client, auth, secure_domain, public_domain):
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

"""
Tests that an AuthPolicy is correctly applied to a specific listener section of
a Gateway, protecting only the traffic handled by that named listener.
It verifies that the targeted listener is protected by the policy, while the
other listener on the same Gateway remains public and unaffected.
"""

import pytest
from testsuite.gateway import GatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.hostname import StaticHostname
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy

pytestmark = [pytest.mark.authorino, pytest.mark.kuadrant_only]

MANAGED_LISTENER_NAME = "managed-listener"
UNMANAGED_LISTENER_NAME = "unmanaged-listener"


@pytest.fixture(scope="module")
def managed_domain(base_domain):
    """Returns the hostname for the secure, targeted listener."""
    return f"secure.{base_domain}"


@pytest.fixture(scope="module")
def unmanaged_domain(base_domain):
    """Returns the hostname for the public, non-targeted listener."""
    return f"public.{base_domain}"


@pytest.fixture(scope="module")
def gateway(gateway: KuadrantGateway, managed_domain, unmanaged_domain):
    """
    Modifies the existing shared gateway for the purposes of this test module
    by adding two specific HTTP listeners (one for the managed and one for the
    unmanaged domain).
    """

    gateway.add_listener(GatewayListener(name=MANAGED_LISTENER_NAME, hostname=managed_domain))
    gateway.add_listener(GatewayListener(name=UNMANAGED_LISTENER_NAME, hostname=unmanaged_domain))

    gateway.wait_for_ready()

    return gateway


@pytest.fixture(scope="module")
def managed_client(gateway, managed_domain):
    """Returns a client for the managed endpoint, which requires auth."""
    return StaticHostname(managed_domain, gateway.get_tls_cert).client()


@pytest.fixture(scope="module")
def unmanaged_client(gateway, unmanaged_domain):
    """Returns a client for the unmanaged (public) endpoint."""
    return StaticHostname(unmanaged_domain, gateway.get_tls_cert).client()


@pytest.fixture(scope="module")
def route(route: HTTPRoute, managed_domain, unmanaged_domain):
    """
    Replaces the hostnames on the existing HTTPRoute
    for the duration of the test module.
    """
    route.remove_all_hostnames()
    route.add_hostname(managed_domain)
    route.add_hostname(unmanaged_domain)
    route.wait_for_ready()

    return route


@pytest.fixture(scope="module")
def authorization(cluster, blame, module_label, oidc_provider, gateway, route):  # pylint: disable=unused-argument
    """Creates an AuthPolicy that targets ONLY the 'secure-listener' section."""
    policy = AuthPolicy.create_instance(
        cluster,
        blame("authz"),
        gateway,
        section_name=MANAGED_LISTENER_NAME,
        labels={"testRun": module_label},
    )
    policy.identity.add_oidc("oidc-auth", oidc_provider.well_known["issuer"])
    return policy


def test_authpolicy_section_targeting_gateway_listener(managed_client, unmanaged_client, auth):
    """
    Tests that an AuthPolicy attached to a specific Gateway listener protects
    only the traffic handled by that listener.
    """

    response = unmanaged_client.get("/get")
    assert response.status_code == 200, "The unmanaged listener should not require auth"

    response = managed_client.get("/get")
    assert response.status_code == 401, "The secure listener should require auth"

    response = managed_client.get("/get", auth=auth)
    assert response.status_code == 200, "The secure listener should allow requests with valid auth"

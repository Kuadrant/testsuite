"""
Tests that an AuthPolicy targeting a single network resource (HTTPRoute or Gateway) only affects that resource,
even when two separate Gateways expose HTTPRoutes declaring an identical hostname and the same backend.

Because both Gateways share the same hostname, requests cannot be disambiguated via DNS. Instead, the test connects
a KuadrantClient directly to each Gateway's external IP and sets the shared hostname in the 'Host' header, which lets
it steer traffic to a specific Gateway regardless of the identical hostnames.
"""

import pytest

from testsuite.gateway import Gateway, GatewayListener, GatewayRoute
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.httpx import KuadrantClient

pytestmark = [pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def gateway2(request, cluster, blame, label, wildcard_domain) -> Gateway:
    """Second Gateway declaring an identical (wildcard) hostname as the first Gateway"""
    gw = KuadrantGateway.create_instance(cluster, blame("gw2"), {"app": label})
    gw.add_listener(GatewayListener(hostname=wildcard_domain))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def route2(request, gateway2, blame, hostname, backend, module_label) -> GatewayRoute:
    """HTTPRoute attached to the second Gateway declaring an identical hostname and the same backend as 'route'"""
    route = HTTPRoute.create_instance(gateway2.cluster, blame("route2"), gateway2, {"app": module_label})
    route.add_hostname(hostname.hostname)
    route.add_backend(backend)
    request.addfinalizer(route.delete)
    route.commit()
    route.wait_for_ready()
    return route


@pytest.fixture(scope="module")
def authorization(authorization):
    """'deny-all' AuthPolicy targeting either 'route' or 'gateway' (the first Gateway) via indirect parametrization"""
    authorization.authorization.add_opa_policy("rego", "allow = false")
    return authorization


@pytest.fixture(scope="module")
def rate_limit():
    """No RateLimitPolicy is needed for this test"""
    return None


@pytest.fixture(scope="module")
def client(route, gateway, hostname):  # pylint: disable=unused-argument
    """Client connecting directly to the first Gateway's IP with the shared hostname in the 'Host' header"""
    client = KuadrantClient(base_url=f"http://{gateway.external_ip()}", headers={"Host": hostname.hostname})
    yield client
    client.close()


@pytest.fixture(scope="module")
def client2(route2, gateway2, hostname):  # pylint: disable=unused-argument
    """Client connecting directly to the second Gateway's IP with the shared hostname in the 'Host' header"""
    client = KuadrantClient(base_url=f"http://{gateway2.external_ip()}", headers={"Host": hostname.hostname})
    yield client
    client.close()


@pytest.mark.parametrize("authorization", ["route", "gateway"], indirect=True)
@pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/pull/2171")
def test_identical_hostnames_multiple_gateways(client, client2):
    """
    Validate that a 'deny-all' AuthPolicy targeting a single network resource on the first Gateway only affects
    traffic through that Gateway, leaving the second Gateway (sharing the identical hostname) unaffected.
    Setup:
        - Two Gateways declaring identical (wildcard) hostnames
        - Two HTTPRoutes, each attached to its own Gateway, declaring the identical hostname and the same backend
        - 'deny-all' AuthPolicy targeting either the first HTTPRoute or the first Gateway (parametrized)
    Test:
        - Send a request through the first Gateway and assert it is denied (403 Forbidden)
        - Send a request through the second Gateway and assert it is allowed (200 OK)
    """
    assert client.get("/get").status_code == 403
    assert client2.get("/get").status_code == 200

"""Tests for PipelinePolicy Gateway-level targeting.

HTTPRoute targeting is the default and is covered by test_pipeline_policy_basic.py.
"""

import pytest

from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kuadrant.extensions.pipeline_policy import PipelinePolicy

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module")
def hostname2(gateway, exposer, blame):
    """Second hostname for the second route"""
    return exposer.expose_hostname(blame("hostname2"), gateway)


@pytest.fixture(scope="module")
def route2(request, gateway, blame, hostname2, backend, module_label):
    """Second HTTPRoute on the same gateway with a different hostname"""
    route = HTTPRoute.create_instance(gateway.cluster, blame("route2"), gateway, {"app": module_label})
    route.add_hostname(hostname2.hostname)
    route.add_backend(backend)
    request.addfinalizer(route.delete)
    route.commit()
    return route


@pytest.fixture(scope="module")
def client2(route2, hostname2):  # pylint: disable=unused-argument
    """Client for the second route"""
    client = hostname2.client()
    yield client
    client.close()


@pytest.fixture(scope="module")
def gateway_policy(cluster, blame, gateway):
    """PipelinePolicy targeting the Gateway with deny and response headers."""
    policy = PipelinePolicy.create_instance(cluster, blame("gw-pp"), gateway)
    policy.on_http_request.add_deny(predicate='request.url_path == "/blocked"', with_status=403)
    policy.on_http_response.add_headers([["x-gateway-policy", "active"]])
    return policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, route2, gateway_policy):  # pylint: disable=unused-argument
    """Commit gateway policy after route2 is ready."""
    request.addfinalizer(gateway_policy.delete)
    gateway_policy.commit()
    gateway_policy.wait_for_ready()


@pytest.mark.parametrize("client_fixture", ["client", "client2"])
def test_gateway_target_affects_routes(request, client_fixture):
    """Request to each route gets pipeline response header when policy targets the gateway."""
    http_client = request.getfixturevalue(client_fixture)
    response = http_client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-gateway-policy") == "active"


@pytest.mark.parametrize("client_fixture", ["client", "client2"])
def test_gateway_target_blocked_path(request, client_fixture):
    """Blocked path is denied on both routes when policy targets the gateway."""
    http_client = request.getfixturevalue(client_fixture)
    response = http_client.get("/blocked")
    assert response.status_code == 403

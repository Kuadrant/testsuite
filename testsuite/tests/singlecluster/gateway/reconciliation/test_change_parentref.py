"""
Test for changing targetRef field in policies (AuthPolicy and RateLimitPolicy)
"""

import pytest

from testsuite.gateway import TLSGatewayListener, GatewayRoute
from testsuite.gateway.envoy.route import EnvoyVirtualRoute
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy


@pytest.fixture(scope="module")
def wildcard_domain2(base_domain):
    """Wildcard domain for Gateway B"""
    return f"*.{base_domain}-b"


@pytest.fixture(scope="module")
def gateway_b(request, cluster, blame, wildcard_domain2, module_label):  # pylint: disable=unused-argument
    """Create and configure Gateway B"""
    gateway_name = blame("gw-b")
    gw = KuadrantGateway.create_instance(cluster, gateway_name, {"app": module_label})
    gw.add_listener(TLSGatewayListener(hostname=wildcard_domain2, gateway_name=gateway_name))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def route_b(request, kuadrant, wildcard_domain2, gateway_b, blame, backend, module_label) -> GatewayRoute:
    """Create and configure Route B"""
    if kuadrant:
        route = HTTPRoute.create_instance(gateway_b.cluster, blame("route-b"), gateway_b, {"app": module_label})
    else:
        route = EnvoyVirtualRoute.create_instance(gateway_b.cluster, blame("route-b"), gateway_b)
    route.add_hostname(wildcard_domain2)
    route.add_backend(backend)
    request.addfinalizer(route.delete)
    route.commit()
    return route


@pytest.fixture(scope="module")
def rate_limit_policy(request, cluster, blame, module_label, gateway):
    """RateLimitPolicy for testing"""
    policy = RateLimitPolicy.create_instance(cluster, blame("limit"), gateway, labels={"testRun": module_label})
    policy.add_limit("basic", [Limit(5, "10s")])
    request.addfinalizer(policy.delete)
    policy.commit()
    return policy


def test_update_ratelimit_policy_target_ref(
    gateway, gateway_b, rate_limit_policy, client, auth, route_b
):  # pylint: disable=unused-argument
    """Test updating the targetRef of a RateLimitPolicy from Gateway A to Gateway B"""
    initial_target_ref = rate_limit_policy.model["spec"]["targetRef"]["name"]
    assert (
        initial_target_ref == gateway.model.metadata.name
    ), f"Initial targetRef mismatch: expected {gateway.model.metadata.name}, got {initial_target_ref}"

    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    rate_limit_policy.wait_for_ready()
    rate_limit_policy.refresh()

    rate_limit_policy.model["spec"]["targetRef"]["name"] = gateway_b.model.metadata.name
    res = rate_limit_policy.apply()
    assert res.status() == 0, res.err()

    rate_limit_policy.refresh()
    updated_target_ref = rate_limit_policy.model["spec"]["targetRef"]["name"]
    assert (
        updated_target_ref == gateway_b.model.metadata.name
    ), f"Updated targetRef mismatch: expected {gateway_b.model.metadata.name}, got {updated_target_ref}"

    response = client.get("/get", auth=auth)
    assert response.status_code == 200


def test_update_auth_policy_target_ref(
    gateway, gateway_b, authorization, client, auth, route_b
):  # pylint: disable=unused-argument
    """Test updating the targetRef of an AuthPolicy from Gateway A to Gateway B"""
    # Update targetRef of the AuthPolicy to point to gateway A
    authorization.model["spec"]["targetRef"] = gateway.reference
    authorization.apply()
    authorization.wait_for_ready()
    authorization.refresh()

    initial_target_ref = authorization.model["spec"]["targetRef"]["name"]
    assert (
        initial_target_ref == gateway.model.metadata.name
    ), f"Initial targetRef mismatch: expected {gateway.model.metadata.name}, got {initial_target_ref}"

    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    authorization.wait_for_ready()
    authorization.refresh()

    authorization.model["spec"]["targetRef"] = gateway_b.reference
    res = authorization.apply()
    assert res.status() == 0, res.err()

    authorization.refresh()
    updated_target_ref = authorization.model["spec"]["targetRef"]["name"]
    assert (
        updated_target_ref == gateway_b.model.metadata.name
    ), f"Updated targetRef mismatch: expected {gateway_b.model.metadata.name}, got {updated_target_ref}"

    response = client.get("/get", auth=auth)
    assert response.status_code == 200

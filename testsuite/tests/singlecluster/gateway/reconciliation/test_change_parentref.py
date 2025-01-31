"""
Test for changing targetRef field in policies (AuthPolicy and RateLimitPolicy)
"""

import pytest

from testsuite.backend.httpbin import Httpbin
from testsuite.gateway import GatewayRoute, GatewayListener, Hostname
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kuadrant.policy.dns import DNSPolicy
from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def wildcard_domain2(base_domain):
    """Wildcard domain for Gateway B"""
    return f"*.{base_domain}"


@pytest.fixture(scope="module")
def gateway(request, kuadrant, cluster, blame, wildcard_domain, module_label):  # pylint: disable=unused-argument
    """Create and configure Gateway A"""
    # Added this gateway because I couldn't get the tests to pass or work as -
    # expected using the existing conftest version
    gw = KuadrantGateway.create_instance(cluster, blame("gw"), {"app": module_label})
    gw.add_listener(GatewayListener(hostname=wildcard_domain))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def gateway_b(request, kuadrant, cluster, blame, wildcard_domain2, module_label):  # pylint: disable=unused-argument
    """Create and configure Gateway B"""
    gw = KuadrantGateway.create_instance(cluster, blame("gw-b"), {"app": module_label})
    gw.add_listener(GatewayListener(hostname=wildcard_domain2))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def hostname_b(gateway_b, exposer, blame) -> Hostname:
    """Expose Hostname for Gateway B"""
    hostname = exposer.expose_hostname(blame("hostname-b"), gateway_b)
    return hostname


@pytest.fixture(scope="session")
def backend_b(request, cluster, blame, label, testconfig):  # pylint: disable=unused-argument
    """Deploys Httpbin backend"""
    # Added to resolve backend errors I was seeing in Gateway B / Route B YAML files
    image = testconfig["httpbin"]["image"]
    httpbin = Httpbin(cluster, blame("httpbin"), label, image)
    httpbin.commit()
    return httpbin


@pytest.fixture(scope="module")
def route_b(
    request, gateway_b, blame, hostname_b, module_label, backend_b
) -> GatewayRoute:  # pylint: disable=unused-argument
    """Create and configure Route B"""
    route = HTTPRoute.create_instance(gateway_b.cluster, blame("route-b"), gateway_b, {"app": module_label})
    route.add_hostname(hostname_b.hostname)
    route.add_backend(backend_b)
    request.addfinalizer(route.delete)
    route.commit()
    route.wait_for_ready()
    return route


@pytest.fixture(scope="module")
def client_b(route_b, hostname_b):  # pylint: disable=unused-argument
    """Returns httpx client for Gateway B"""
    client = hostname_b.client()
    yield client
    client.close()


@pytest.fixture(scope="module")
def rate_limit_policy(request, cluster, blame, module_label, gateway, route_b):  # pylint: disable=unused-argument
    """RateLimitPolicy for testing"""
    policy = RateLimitPolicy.create_instance(cluster, blame("limit"), gateway, labels={"testRun": module_label})
    policy.add_limit("basic", [Limit(5, "10s")])
    request.addfinalizer(policy.delete)
    policy.commit()
    return policy


@pytest.fixture(scope="module")
def dns_policy_b(blame, gateway_b, module_label, dns_provider_secret, request):
    """DNSPolicy fixture for Gateway B"""
    # Added to resolve DNS errors I was seeing in Gateway B / Route B YAML files
    policy = DNSPolicy.create_instance(
        gateway_b.cluster, blame("dns-b"), gateway_b, dns_provider_secret, labels={"app": module_label}
    )
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()
    return policy


def test_update_ratelimit_policy_target_ref(
    gateway, gateway_b, rate_limit_policy, client, client_b, auth, blame, dns_policy_b
):  # pylint: disable=unused-argument
    """Test updating the targetRef of a RateLimitPolicy from Gateway A to Gateway B"""
    # Kept auth=auth as removing it results in an 'HTTP 401 Unauthorized' error
    responses = client.get_many("/get", 5, auth=auth)
    responses.assert_all(status_code=200)
    assert client.get("/get", auth=auth).status_code == 429

    rate_limit_policy.refresh().model.spec.targetRef.name = gateway_b.model.metadata.name
    res = rate_limit_policy.apply()
    assert res.status() == 0, res.err()
    rate_limit_policy.wait_for_ready()

    responses = client_b.get_many("/get", 5, auth=auth)
    responses.assert_all(status_code=200)
    assert client_b.get("/get", auth=auth).status_code == 429


def test_update_auth_policy_target_ref(
    gateway, gateway_b, authorization, client, client_b, auth, blame, dns_policy_b
):  # pylint: disable=unused-argument
    """Test updating the targetRef of an AuthPolicy from Gateway A to Gateway B"""
    # Overwriting this because the higher-level conftest sets a wrong targetRef for this tests purpose
    authorization.model.spec.targetRef = gateway.reference
    authorization.apply()
    authorization.wait_for_ready()
    authorization.refresh()

    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    authorization.refresh().model.spec.targetRef = gateway_b.reference
    res = authorization.apply()
    assert res.status() == 0, res.err()
    authorization.wait_for_ready()

    response = client_b.get("/get", auth=auth)
    assert response.status_code == 200

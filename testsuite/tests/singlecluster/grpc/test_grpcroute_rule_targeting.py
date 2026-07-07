"""Tests that the RLP is correctly applied to a specific GRPCRoute rule"""

import pytest
from grpc import StatusCode

from testsuite.gateway import GRPCRouteMatch, GRPCMethodMatch
from testsuite.gateway.gateway_api.grpc_route import GRPCRoute
from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy

pytestmark = [pytest.mark.limitador]

LIMIT = Limit(2, "10s")


@pytest.fixture(scope="module")
def authorization():
    """No AuthPolicy needed for this test"""
    return None


@pytest.fixture(scope="module")
def route(request, gateway, blame, hostname, backend, module_label):
    """GRPCRoute with two rules targeting different methods"""
    route = GRPCRoute.create_instance(gateway.cluster, blame("route"), gateway, {"app": module_label})
    route.add_hostname(hostname.hostname)
    route.add_rule(backend, GRPCRouteMatch(method=GRPCMethodMatch(type="Exact", method="HeadersUnary")))  # rule-1
    route.add_rule(backend, GRPCRouteMatch(method=GRPCMethodMatch(type="Exact", method="DummyUnary")))  # rule-2
    request.addfinalizer(route.delete)
    route.commit()
    route.wait_for_ready()
    return route


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, route):
    """Add a RateLimitPolicy targeting the first GRPCRoute Rule"""
    rlp = RateLimitPolicy.create_instance(cluster, blame("limit"), route, "rule-1", labels={"testRun": module_label})
    rlp.add_limit("basic", [LIMIT])
    return rlp


def test_limit_match_grpcroute_rule(client):
    """Tests that RLP correctly applies to the specific GRPCRoute Rule"""
    responses = client.call_many("/HeadersUnary", LIMIT.limit)
    responses.assert_all(status_code=StatusCode.OK)
    assert client.call("/HeadersUnary").status_code == StatusCode.UNAVAILABLE

    assert client.call("/DummyUnary").status_code == StatusCode.OK

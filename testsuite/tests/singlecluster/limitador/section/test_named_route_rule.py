"""Tests that the RLP is correctly applied to the specific named route rule"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy

pytestmark = [pytest.mark.limitador]


@pytest.fixture(scope="module")
def route(route, backend):
    """Add two named backend rules for different paths to the route"""
    route.remove_all_rules()
    route.add_backend(backend, "/get", name="get-rule")
    route.add_backend(backend, "/anything", name="anything-rule")
    return route


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, route):
    """Add a RateLimitPolicy targeting the get-rule HTTPRoute Rule."""
    rlp = RateLimitPolicy.create_instance(cluster, blame("limit"), route, "get-rule", labels={"testRun": module_label})
    rlp.add_limit("basic", [Limit(2, "10s")])
    return rlp


def test_limit_match_named_route_rule(client):
    """Tests that RLP correctly applies to the specific named HTTPRoute Rule"""
    responses = client.get_many("/get", 2)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429

    response = client.get("/anything")
    assert response.status_code == 200
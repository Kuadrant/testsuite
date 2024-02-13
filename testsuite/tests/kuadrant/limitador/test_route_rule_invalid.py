"""Tests that RLP for a HTTPRouteRule doesn't take effect if there isn't a exact matching HTTPRouteRule"""

import pytest

from testsuite.gateway import RouteMatch, PathMatch, MatchType, HTTPMethod
from testsuite.policy.rate_limit_policy import Limit, RouteSelector


@pytest.fixture(scope="module", params=["/anything/get", "/anything", "/get"])
def endpoint(request):
    """Endpoints to apply a RLP to"""
    return request.param


@pytest.fixture(scope="module")
def route(route, backend):
    """Add new rule to the route"""
    route.remove_all_rules()
    route.add_rule(
        backend,
        RouteMatch(path=PathMatch(value="/anything", type=MatchType.PATH_PREFIX), method=HTTPMethod.GET),
    )
    route.add_rule(
        backend,
        RouteMatch(path=PathMatch(value="/get", type=MatchType.PATH_PREFIX), method=HTTPMethod.GET),
    )
    return route


@pytest.fixture(scope="module")
def rate_limit(rate_limit, endpoint):
    """Add limit to the policy"""
    selector = RouteSelector(RouteMatch(path=PathMatch(value=endpoint, type=MatchType.EXACT), method=HTTPMethod.GET))
    rate_limit.add_limit("basic", [Limit(5, 10)], route_selectors=[selector])
    return rate_limit


def test_route_rule_invalid(client, endpoint):
    """Tests that RLP for a HTTPRouteRule doesn't apply if there isn't an exact match"""
    responses = client.get_many(endpoint, 5)
    assert all(
        r.status_code == 200 for r in responses
    ), f"Rate Limited resource unexpectedly rejected requests {responses}"
    assert client.get(endpoint).status_code == 200

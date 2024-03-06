"""Tests that RLP for a HTTPRouteRule doesn't affect the HTTPRoute with same path but different method"""

import pytest

from testsuite.gateway import RouteMatch, PathMatch, MatchType, HTTPMethod
from testsuite.policy.rate_limit_policy import Limit, RouteSelector


pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


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
        RouteMatch(path=PathMatch(value="/anything", type=MatchType.PATH_PREFIX), method=HTTPMethod.POST),
    )
    return route


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to the policy"""
    selector = RouteSelector(
        RouteMatch(path=PathMatch(value="/anything", type=MatchType.PATH_PREFIX), method=HTTPMethod.GET)
    )
    rate_limit.add_limit("anything", [Limit(5, 10)], route_selectors=[selector])
    return rate_limit


def test_route_subset_method(client):
    """Tests that RLP for a HTTPRouteRule doesn't apply to separate HTTPRouteRule with different method"""
    responses = client.get_many("/anything", 5)
    assert all(
        r.status_code == 200 for r in responses
    ), f"Rate Limited resource unexpectedly rejected requests {responses}"
    assert client.get("/anything").status_code == 429
    assert client.post("/anything").status_code == 200

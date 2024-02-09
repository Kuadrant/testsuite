"""Tests that RLP for a child of HTTPRouteRule doesn't take effect if there isn't a matching HTTPRouteRule"""

import pytest

from testsuite.gateway import RouteMatch, PathMatch, MatchType, HTTPMethod
from testsuite.policy.rate_limit_policy import Limit, RouteSelector


@pytest.fixture(scope="module")
def route(route, backend):
    """Add new rule to the route"""
    route.remove_all_rules()
    route.add_rule(
        backend,
        RouteMatch(path=PathMatch(value="/anything", type=MatchType.PATH_PREFIX), method=HTTPMethod.GET),
    )
    return route


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to the policy"""
    selector = RouteSelector(
        RouteMatch(path=PathMatch(value="/anything/get", type=MatchType.EXACT), method=HTTPMethod.GET)
    )
    rate_limit.add_limit("subset", [Limit(5, 10)], route_selectors=[selector])
    return rate_limit


def test_route_rule_child(client):
    """Tests that RLP for a child of HTTPRoute rule doesn't apply to the parent HTTPRoute rule"""
    responses = client.get_many("/anything/get", 5)
    assert all(
        r.status_code == 200 for r in responses
    ), f"Rate Limited resource unexpectedly rejected requests {responses}"
    assert client.get("/anything/get").status_code == 200

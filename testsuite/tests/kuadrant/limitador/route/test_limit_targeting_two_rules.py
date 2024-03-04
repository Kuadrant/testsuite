"""Tests that one RLP limit targeting two rules limits them together"""

import pytest

from testsuite.gateway import RouteMatch, PathMatch, MatchType
from testsuite.policy.rate_limit_policy import RouteSelector, Limit


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to the policy"""
    selector = RouteSelector(
        RouteMatch(path=PathMatch(value="/get", type=MatchType.PATH_PREFIX)),
        RouteMatch(path=PathMatch(value="/anything", type=MatchType.PATH_PREFIX)),
    )
    rate_limit.add_limit("test", [Limit(5, 10)], route_selectors=[selector])
    return rate_limit


def test_limit_targeting_two_rules(client):
    """Tests that one RLP limit targeting two rules limits them together"""
    responses = client.get_many("/get", 3)
    assert all(
        r.status_code == 200 for r in responses
    ), f"Rate Limited resource unexpectedly rejected requests {responses}"

    responses = client.get_many("/anything", 2)
    assert all(
        r.status_code == 200 for r in responses
    ), f"Rate Limited resource unexpectedly rejected requests {responses}"

    assert client.get("/get").status_code == 429
    assert client.get("/anything").status_code == 429

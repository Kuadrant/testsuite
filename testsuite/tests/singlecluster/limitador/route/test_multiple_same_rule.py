"""Test that multiple limits targeting same rule are correctly applied"""

import pytest

from testsuite.gateway import RouteMatch, PathMatch, MatchType
from testsuite.kuadrant.policy.rate_limit import RouteSelector, Limit


pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to the policy"""
    selector = RouteSelector(
        RouteMatch(path=PathMatch(value="/get", type=MatchType.PATH_PREFIX)),
    )
    rate_limit.add_limit("test1", [Limit(8, 10)], route_selectors=[selector])
    rate_limit.add_limit("test2", [Limit(3, 5)], route_selectors=[selector])
    return rate_limit


def test_two_rules_targeting_one_limit(client):
    """Test that one limit ends up shadowing others"""
    responses = client.get_many("/get", 3)
    assert all(
        r.status_code == 200 for r in responses
    ), f"Rate Limited resource unexpectedly rejected requests {responses}"
    assert client.get("/get").status_code == 429

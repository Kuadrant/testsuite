"""Tests that the RLP is correctly apply to the route rule"""

import pytest

from testsuite.gateway import RouteMatch, PathMatch, MatchType
from testsuite.policy.rate_limit_policy import Limit, RouteSelector

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to the policy"""
    selector = RouteSelector(
        RouteMatch(path=PathMatch(value="/get", type=MatchType.PATH_PREFIX)),
        RouteMatch(path=PathMatch(value="/anything/test", type=MatchType.PATH_PREFIX)),
    )
    rate_limit.add_limit("multiple", [Limit(5, 10)], route_selectors=[selector])
    return rate_limit


def test_rule_match(client):
    """Tests that RLP correctly applies to the given HTTPRoute rule"""
    responses = client.get_many("/get", 5)
    responses.assert_all(status_code=200)

    assert client.get("/get").status_code == 429

    response = client.get("/anything")
    assert response.status_code == 200


def test_rule_missmatch(client):
    """Tests that RLP is not applied for not existing route rule"""
    responses = client.get_many("/anything/test", 7)
    responses.assert_all(status_code=200)

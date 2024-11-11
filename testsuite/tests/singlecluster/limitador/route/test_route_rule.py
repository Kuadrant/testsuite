"""Tests that the RLP is correctly apply to the route rule"""

import pytest

from testsuite.kuadrant.policy import CelPredicate
from testsuite.kuadrant.policy.rate_limit import Limit

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to the policy"""
    rate_limit.add_limit("multiple", [Limit(5, "10s")], when=[CelPredicate("request.path == '/get'")])
    return rate_limit


@pytest.mark.issue("https://github.com/Kuadrant/testsuite/issues/561")
def test_rule_match(client):
    """Tests that RLP correctly applies to the given HTTPRoute rule"""
    responses = client.get_many("/get", 5)
    responses.assert_all(status_code=200)

    assert client.get("/get").status_code == 429

    response = client.get("/anything")
    assert response.status_code == 200

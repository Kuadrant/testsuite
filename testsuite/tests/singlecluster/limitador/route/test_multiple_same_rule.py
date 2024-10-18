"""Test that multiple limits targeting same rule are correctly applied"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.kuadrant.policy.authorization import Pattern


pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to the policy"""
    when = Pattern("request.path", "eq", "/get")
    rate_limit.add_limit("test1", [Limit(8, 10)], when=[when])
    rate_limit.add_limit("test2", [Limit(3, 5)], when=[when])
    return rate_limit


@pytest.mark.issue("https://github.com/Kuadrant/testsuite/issues/561")
def test_two_rules_targeting_one_limit(client):
    """Test that one limit ends up shadowing others"""
    responses = client.get_many("/get", 3)
    assert all(
        r.status_code == 200 for r in responses
    ), f"Rate Limited resource unexpectedly rejected requests {responses}"
    assert client.get("/get").status_code == 429

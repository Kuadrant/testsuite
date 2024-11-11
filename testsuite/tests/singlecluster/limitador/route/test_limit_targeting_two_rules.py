"""Tests that one RLP limit targeting two rules limits them together"""

import pytest

from testsuite.kuadrant.policy import CelPredicate
from testsuite.kuadrant.policy.rate_limit import Limit


pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to the policy"""
    rate_limit.add_limit("test", [Limit(5, "10s")], when=[CelPredicate("request.method == 'GET'")])
    return rate_limit


@pytest.mark.issue("https://github.com/Kuadrant/testsuite/issues/561")
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

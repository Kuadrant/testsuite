"""
Tests that a single limit is enforced as expected over multiple iterations
"""

from time import sleep

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit

pytestmark = [pytest.mark.limitador]


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to the policy"""
    rate_limit.add_limit("multiple", [Limit(5, "10s")])
    return rate_limit


@pytest.mark.parametrize("rate_limit", ["route", "gateway"], indirect=True)
def test_multiple_iterations(client):
    """Tests that simple limit is applied successfully and works for multiple iterations"""
    for _ in range(10):
        responses = client.get_many("/get", 5)
        responses.assert_all(status_code=200)
        assert client.get("/get").status_code == 429
        sleep(10)

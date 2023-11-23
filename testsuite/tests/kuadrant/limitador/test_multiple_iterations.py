"""
Tests that a single limit is enforced as expected over multiple iterations
"""
from time import sleep

import pytest

from testsuite.policy.rate_limit_policy import Limit


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to the policy"""
    rate_limit.add_limit("multiple", [Limit(5, 10)])
    return rate_limit


def test_multiple_iterations(client):
    """Tests that simple limit is applied successfully and works for multiple iterations"""
    for _ in range(10):
        responses = client.get_many("/get", 5)
        assert all(
            r.status_code == 200 for r in responses
        ), f"Rate Limited resource unexpectedly rejected requests {responses}"
        assert client.get("/get").status_code == 429
        sleep(10)

"""
Tests that a single limit is enforced as expected over one iteration
"""

import pytest

from testsuite.policy.rate_limit_policy import Limit


@pytest.fixture(
    scope="module",
    params=[
        pytest.param(Limit(2, 15), id="2 requests every 15 sec"),
        pytest.param(Limit(5, 10), id="5 requests every 10 sec"),
        pytest.param(Limit(3, 5), id="3 request every 5 sec"),
    ],
)
def limit(request):
    """Combination of max requests and time period"""
    return request.param


@pytest.fixture(scope="module")
def rate_limit(rate_limit, limit):
    """Add limit to the policy"""
    rate_limit.add_limit("basic", [limit])
    return rate_limit


def test_limit(client, limit):
    """Tests that simple limit is applied successfully"""
    responses = client.get_many("/get", limit.limit)
    assert all(
        r.status_code == 200 for r in responses
    ), f"Rate Limited resource unexpectedly rejected requests {responses}"
    assert client.get("/get").status_code == 429

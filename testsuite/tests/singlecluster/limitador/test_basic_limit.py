"""
Tests that a single limit is enforced as expected over one iteration
"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(
    scope="module",
    params=[
        pytest.param(Limit(2, "15s"), id="2 requests every 15 sec"),
        pytest.param(Limit(5, "10s"), id="5 requests every 10 sec"),
        pytest.param(Limit(3, "5s"), id="3 request every 5 sec"),
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


@pytest.mark.parametrize("rate_limit", ["route", "gateway"], indirect=True)
def test_limit(client, limit):
    """Tests that simple limit is applied successfully"""
    responses = client.get_many("/get", limit.limit)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429

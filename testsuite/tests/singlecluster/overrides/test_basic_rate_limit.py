"""Test basic enforcement of the rules inside the 'overrides' block of the RateLimitPolicy assigned to a Gateway"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]

LIMIT = Limit(3, 5)


@pytest.fixture(scope="module")
def authorization():
    """No authorization is required for this test"""
    return None


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add basic requests limit to overrides block of RateLimitPolicy"""
    rate_limit.overrides.add_limit("basic", [LIMIT])
    return rate_limit


@pytest.mark.parametrize("rate_limit", ["gateway"], indirect=True)
def test_basic_rate_limit(rate_limit, route, client):
    """Test if rules inside overrides block of Gateway's RateLimitPolicy are inherited by the HTTPRoute
    and enforced like any other normal rule"""
    route.refresh()
    assert route.is_affected_by(rate_limit)

    responses = client.get_many("/get", LIMIT.limit)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429  # assert that RateLimitPolicy is enforced

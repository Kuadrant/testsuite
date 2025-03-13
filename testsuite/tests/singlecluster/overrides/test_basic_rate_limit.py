"""Test enforcement of the rules inside the 'overrides' block of the RateLimitPolicy assigned to a Gateway/HTTPRoute"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]

OVERRIDE_LIMIT = Limit(3, "5s")
ROUTE_LIMIT = Limit(2, "5s")


@pytest.fixture(scope="module")
def authorization():
    """No authorization is required for this test"""
    return None


@pytest.fixture(scope="function")
def rate_limit_route(request, cluster, blame, module_label, route):
    """Add a RateLimitPolicy to the HTTPRoute with a basic limit to be overridden."""
    rate_limit_route = RateLimitPolicy.create_instance(
        cluster, blame("limit-route"), route, labels={"testRun": module_label}
    )
    rate_limit_route.add_limit("basic", [ROUTE_LIMIT])
    request.addfinalizer(rate_limit_route.delete)
    rate_limit_route.commit()
    rate_limit_route.wait_for_accepted()
    return rate_limit_route


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add an override to RateLimitPolicy"""
    rate_limit.overrides.add_limit("override-limit", [OVERRIDE_LIMIT])
    return rate_limit


@pytest.mark.parametrize("rate_limit", ["route", "gateway"], indirect=True)
def test_basic_rate_limit(rate_limit, rate_limit_route, route, client):
    """Test if rules inside overrides block of Gateway/HTTPRoute RateLimitPolicy are inherited by the HTTPRoute
    and override the rate limit targeting the route."""
    route.refresh()
    assert route.is_affected_by(rate_limit)
    assert route.is_affected_by(rate_limit_route)

    responses = client.get_many("/get", OVERRIDE_LIMIT.limit)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429  # assert that RateLimitPolicy is enforced

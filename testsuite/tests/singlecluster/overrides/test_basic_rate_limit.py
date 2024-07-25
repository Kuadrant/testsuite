"""Test basic enforcement of the rules inside the 'overrides' block of the RateLimitPolicy assigned to a Gateway"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]

GATEWAY_LIMIT = Limit(3, 5)
ROUTE_LIMIT = Limit(2, 5)


@pytest.fixture(scope="module")
def authorization():
    """No authorization is required for this test"""
    return None


@pytest.fixture(scope="module")
def rate_limit_gw(request, cluster, blame, module_label, gateway):
    """Add a RateLimitPolicy to the Gateway with an overrides block to override the Route-level policy."""
    rate_limit_gateway = RateLimitPolicy.create_instance(
        cluster, blame("limit-gateway"), gateway, labels={"testRun": module_label}
    )
    rate_limit_gateway.overrides.add_limit("basic", [GATEWAY_LIMIT])
    request.addfinalizer(rate_limit_gateway.delete)
    rate_limit_gateway.commit()
    rate_limit_gateway.wait_for_ready()
    return rate_limit_gateway


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add basic requests limit to RateLimitPolicy"""
    rate_limit.add_limit("basic", [ROUTE_LIMIT])
    return rate_limit


def test_basic_rate_limit(rate_limit, rate_limit_gw, route, client):
    """Test if rules inside overrides block of Gateway's RateLimitPolicy are inherited by the HTTPRoute
    and enforced like any other normal rule"""
    route.refresh()
    assert route.is_affected_by(rate_limit)
    rate_limit_gw.wait_for_full_enforced()

    responses = client.get_many("/get", GATEWAY_LIMIT.limit)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429  # assert that RateLimitPolicy is enforced

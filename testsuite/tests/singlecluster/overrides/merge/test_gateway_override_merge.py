"""Test override overriding another policy aimed at the same Gateway Listener."""

import pytest

from testsuite.kuadrant.policy import CelPredicate
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit, Strategy

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture(scope="function")
def override_rate_limit(cluster, blame, module_label, gateway):
    """Add a RateLimitPolicy with a merge strategy override targeting a specific endpoint."""
    override_rate_limit = RateLimitPolicy.create_instance(
        cluster, blame("limit"), gateway, labels={"testRun": module_label}
    )
    when = CelPredicate("request.path == '/get'")
    override_rate_limit.overrides.add_limit("route_limit", [Limit(3, "5s")], when=[when])
    override_rate_limit.overrides.strategy(Strategy.MERGE)
    return override_rate_limit


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limits targeted at specific endpoints to the RateLimitPolicy."""
    gateway_when = CelPredicate("request.path == '/anything'")
    rate_limit.add_limit("gateway_limit", [Limit(3, "5s")], when=[gateway_when])
    route_when = CelPredicate("request.path == '/get'")
    rate_limit.add_limit("route_limit", [Limit(10, "5s")], when=[route_when])
    return rate_limit


@pytest.fixture(scope="function", autouse=True)
def commit(request, route, rate_limit, override_rate_limit):  # pylint: disable=unused-argument
    """Commits RateLimitPolicy after the HTTPRoute is created"""
    for policy in [override_rate_limit, rate_limit]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_accepted()


@pytest.mark.parametrize("rate_limit", ["gateway", "route"], indirect=True)
def test_gateway_override_merge(client):
    """Test RateLimitPolicy with an override and merge strategy overriding only a part of a new policy."""
    get = client.get_many("/get", 3)
    get.assert_all(status_code=200)
    assert client.get("/get").status_code == 429

    anything = client.get_many("/anything", 3)
    anything.assert_all(status_code=200)
    assert client.get("/anything").status_code == 429

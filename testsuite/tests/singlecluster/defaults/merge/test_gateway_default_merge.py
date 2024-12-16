"""Test gateway level default merging with and being patrially overriden by another policy."""

import pytest

from testsuite.kuadrant.policy import CelPredicate
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit, Strategy

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Create a RateLimitPolicy with a basic limit with same target as one default."""
    when = CelPredicate("request.path == '/get'")
    rate_limit.add_limit("route_limit", [Limit(3, "5s")], when=[when])
    return rate_limit


@pytest.fixture(scope="module")
def global_rate_limit(cluster, blame, module_label, gateway):
    """Create a RateLimitPolicy with default policies and a merge strategy."""
    global_rate_limit = RateLimitPolicy.create_instance(
        cluster, blame("limit"), gateway, labels={"testRun": module_label}
    )
    gateway_when = CelPredicate("request.path == '/anything'")
    global_rate_limit.defaults.add_limit("gateway_limit", [Limit(3, "5s")], when=[gateway_when])
    route_when = CelPredicate("request.path == '/get'")
    global_rate_limit.defaults.add_limit("route_limit", [Limit(10, "5s")], when=[route_when])
    global_rate_limit.defaults.strategy(Strategy.MERGE)
    return global_rate_limit


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, rate_limit, global_rate_limit):  # pylint: disable=unused-argument
    """Commits RateLimitPolicy after the HTTPRoute is created"""
    for policy in [global_rate_limit, rate_limit]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_ready()


@pytest.mark.parametrize("rate_limit", ["gateway", "route"], indirect=True)
def test_gateway_default_merge(client):
    """Test Gateway default policy being partially overriden when another policy with the same target is created."""
    get = client.get_many("/get", 3)
    get.assert_all(status_code=200)
    assert client.get("/get").status_code == 429

    anything = client.get_many("/anything", 3)
    anything.assert_all(status_code=200)
    assert client.get("/anything").status_code == 429

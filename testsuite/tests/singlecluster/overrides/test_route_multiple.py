"""Test override overriding another policy targeting the same HTTPRoute."""

import pytest

from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit

pytestmark = [pytest.mark.kuadrant_only]

LIMIT = Limit(10, "10s")
OVERRIDE_LIMIT = Limit(5, "10s")


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, route):
    """Add a RateLimitPolicy targeting the first HTTPRouteRule."""
    rate_limit = RateLimitPolicy.create_instance(cluster, blame("limit"), route, labels={"testRun": module_label})
    rate_limit.defaults.add_limit("basic", [LIMIT])
    return rate_limit


@pytest.fixture(scope="module")
def override_rate_limit(cluster, blame, module_label, route):
    """Add a RateLimitPolicy targeting the first HTTPRouteRule."""
    override_rate_limit = RateLimitPolicy.create_instance(
        cluster, blame("limit"), route, labels={"testRun": module_label}
    )
    override_rate_limit.overrides.add_limit("override", [OVERRIDE_LIMIT])
    return override_rate_limit


@pytest.fixture(scope="module", autouse=True)
def commit(request, rate_limit, override_rate_limit):  # pylint: disable=unused-argument
    """Commits RateLimitPolicy after the HTTPRoute is created"""
    for policy in [rate_limit, override_rate_limit]:
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_ready()


def test_multiple_policies_route_override(client):
    """Test RateLimitPolicy with an override overriding a default policy targeting the same HTTPRoute"""
    responses = client.get_many("/get", OVERRIDE_LIMIT.limit)
    assert all(
        r.status_code == 200 for r in responses
    ), f"Rate Limited resource unexpectedly rejected requests {responses}"
    assert client.get("/get").status_code == 429

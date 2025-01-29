"""Test override overriding another policy aimed at the same Gateway."""

import pytest

from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit

pytestmark = [pytest.mark.kuadrant_only]

LIMIT = Limit(10, "10s")
OVERRIDE_LIMIT = Limit(5, "10s")


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, gateway):
    """Add a RateLimitPolicy with a default limit targeting the Gateway."""
    rate_limit = RateLimitPolicy.create_instance(cluster, blame("limit"), gateway, labels={"testRun": module_label})
    rate_limit.defaults.add_limit("basic", [LIMIT])
    return rate_limit


@pytest.fixture(scope="module")
def override_rate_limit(cluster, blame, module_label, gateway):
    """Add a RateLimitPolicy with an overrride targeting the Gateway."""
    override_rate_limit = RateLimitPolicy.create_instance(
        cluster, blame("limit"), gateway, labels={"testRun": module_label}
    )
    override_rate_limit.overrides.add_limit("override", [OVERRIDE_LIMIT])
    return override_rate_limit


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, rate_limit, override_rate_limit):  # pylint: disable=unused-argument
    """Commits RateLimitPolicies after the HTTPRoute is created and checks correct status"""
    for policy in [rate_limit, override_rate_limit]:
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_ready()


def test_multiple_policies_gateway_override(client):
    """Test RateLimitPolicy with an override overriding a default policy targeting the same Gateway."""
    responses = client.get_many("/get", OVERRIDE_LIMIT.limit)
    assert all(
        r.status_code == 200 for r in responses
    ), f"Rate Limited resource unexpectedly rejected requests {responses}"
    assert client.get("/get").status_code == 429

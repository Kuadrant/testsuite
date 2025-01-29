"""Test override overriding another policy aimed at the same Gateway Listener."""

import pytest

from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit

pytestmark = [pytest.mark.kuadrant_only]

LIMIT = Limit(8, "5s")
OVERRIDE_LIMIT = Limit(6, "5s")


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, route):
    """Add a RateLimitPolicy targeting the first HTTPRouteRule."""
    rate_limit = RateLimitPolicy.create_instance(
        cluster, blame("limit"), route, "rule-1", labels={"testRun": module_label}
    )
    rate_limit.defaults.add_limit("basic", [LIMIT])
    return rate_limit


@pytest.fixture(scope="module")
def override_rate_limit(cluster, blame, module_label, route):
    """Add a RateLimitPolicy targeting the first HTTPRouteRule."""
    override_rate_limit = RateLimitPolicy.create_instance(
        cluster, blame("limit"), route, "rule-1", labels={"testRun": module_label}
    )
    override_rate_limit.overrides.add_limit("override", [OVERRIDE_LIMIT])
    return override_rate_limit


def test_multiple_policies_rule_override(client):
    """Test RateLimitPolicy with an override overriding a default policy targeting the same HTTPRouteRule"""
    responses = client.get_many("/get", OVERRIDE_LIMIT.limit)
    assert all(
        r.status_code == 200 for r in responses
    ), f"Rate Limited resource unexpectedly rejected requests {responses}"
    assert client.get("/get").status_code == 429

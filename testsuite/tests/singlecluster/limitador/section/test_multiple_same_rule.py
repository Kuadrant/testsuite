"""Test that multiple limits targeting same rule are correctly applied"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy


pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, route):
    """Add a RateLimitPolicy targeting the first HTTPRoute Rule with two limits"""
    rate_limit = RateLimitPolicy.create_instance(
        cluster, blame("limit"), route, "rule-1", labels={"testRun": module_label}
    )
    rate_limit.add_limit("test1", [Limit(8, "10s")])
    rate_limit.add_limit("test2", [Limit(3, "5s")])
    return rate_limit


def test_two_limits_targeting_one_route_rule(client):
    """Test that one limit ends up shadowing others"""
    responses = client.get_many("/get", 3)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429

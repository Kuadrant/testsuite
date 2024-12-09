"""Tests that the RLP is correctly applied to the route rule"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, route):
    """Add a RateLimitPolicy targeting the first HTTPRouteRule."""
    rlp = RateLimitPolicy.create_instance(cluster, blame("limit"), route, "rule-1", labels={"testRun": module_label})
    rlp.add_limit("basic", [Limit(5, "10s")])
    return rlp


def test_rule_match(client):
    """Tests that RLP correctly applies to the given HTTPRouteRule"""
    responses = client.get_many("/get", 5)
    responses.assert_all(status_code=200)

    assert client.get("/get").status_code == 429

    response = client.get("/anything")
    assert response.status_code == 200

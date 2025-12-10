"""Tests that the RLP is correctly applied to the specific route rule"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy

pytestmark = [pytest.mark.limitador]


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, route):
    """Add a RateLimitPolicy targeting the first HTTPRoute Rule."""
    rlp = RateLimitPolicy.create_instance(cluster, blame("limit"), route, "rule-1", labels={"testRun": module_label})
    rlp.add_limit("basic", [Limit(2, "10s")])
    return rlp


def test_limit_match_route_rule(client):
    """Tests that RLP correctly applies to the specific HTTPRoute Rule"""
    responses = client.get_many("/get", 2)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429

    response = client.get("/anything")
    assert response.status_code == 200

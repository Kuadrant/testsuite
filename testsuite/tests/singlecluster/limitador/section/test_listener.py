"""Tests that the RLP is correctly applies to the Gateway Listener."""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, gateway):
    """Add a RateLimitPolicy targeting the Gateway Listener."""
    rlp = RateLimitPolicy.create_instance(cluster, blame("limit"), gateway, "api", labels={"testRun": module_label})
    rlp.add_limit("basic", [Limit(5, "10s")])
    return rlp


def test_listener_match(client):
    """Tests that RLP correctly applies to the given Gateway Listener"""
    responses = client.get_many("/get", 5)
    responses.assert_all(status_code=200)

    assert client.get("/get").status_code == 429
    assert client.get("/anything").status_code == 429

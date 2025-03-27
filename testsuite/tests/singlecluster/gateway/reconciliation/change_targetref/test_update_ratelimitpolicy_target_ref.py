"""
Test for changing targetRef field in RateLimitPolicy
"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy, pytest.mark.limitador]


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, gateway, route):  # pylint: disable=unused-argument
    """RateLimitPolicy for testing"""
    policy = RateLimitPolicy.create_instance(cluster, blame("limit"), gateway, labels={"testRun": module_label})
    policy.add_limit("basic", [Limit(2, "10s")])
    return policy


def test_update_ratelimit_policy_target_ref(
    route2, gateway2, rate_limit, client, client2, dns_policy, dns_policy2, change_target_ref
):  # pylint: disable=unused-argument
    """Test updating the targetRef of a RateLimitPolicy from Gateway 1 to Gateway 2"""
    responses = client.get_many("/get", 2)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429

    responses = client2.get_many("/get", 3)
    responses.assert_all(status_code=200)

    change_target_ref(rate_limit, gateway2)

    responses = client2.get_many("/get", 2)
    responses.assert_all(status_code=200)
    assert client2.get("/get").status_code == 429

    responses = client.get_many("/get", 3)
    responses.assert_all(status_code=200)

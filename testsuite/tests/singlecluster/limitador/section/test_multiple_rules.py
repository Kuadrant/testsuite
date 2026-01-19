"""Test multiple RLP's targeting different HTTPRoute Rules do not interfere with each other"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy

pytestmark = [pytest.mark.limitador]


@pytest.fixture(scope="module")
def rate_limit(cluster, blame, module_label, route):
    """Add a RateLimitPolicy targeting the first HTTPRoute Rule"""
    rate_limit = RateLimitPolicy.create_instance(
        cluster, blame("limit"), route, "rule-1", labels={"testRun": module_label}
    )
    rate_limit.add_limit("basic", [Limit(3, "5s")])
    return rate_limit


@pytest.fixture(scope="module")
def rate_limit2(cluster, blame, module_label, route):
    """Add a RateLimitPolicy targeting the second HTTPRoute Rule"""
    rlp = RateLimitPolicy.create_instance(cluster, blame("limit"), route, "rule-2", labels={"testRun": module_label})
    rlp.add_limit("basic", [Limit(2, "5s")])
    return rlp


@pytest.fixture(scope="module", autouse=True)
def commit(request, rate_limit, rate_limit2):
    """Commit and wait for RateLimitPolicies to be fully enforced"""
    for policy in [rate_limit, rate_limit2]:
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_ready()


def test_multiple_limits_targeting_different_route_rules(client):
    """Test targeting separate HTTPRoute Rules with different limits"""
    responses = client.get_many("/get", 3)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429

    responses = client.get_many("/anything", 2)
    responses.assert_all(status_code=200)
    assert client.get("/anything").status_code == 429

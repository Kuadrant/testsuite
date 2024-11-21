"""
There used to be a limitation if using one HTTPRoute declaring the same hostname as parent Gateway related to RLP.
https://github.com/Kuadrant/kuadrant-operator/blob/3b8e313d552090c52d8aadca95f6952f42a03192/doc/rate-limiting.md#limitation-multiple-network-resources-with-identical-hostnames
(second topology mentioned there)
This test validates that it has been properly fixed, i.e. both RateLimitPolicies (RLPs) are successfully enforced.
"""

from time import sleep
import pytest

from testsuite.kuadrant.policy import has_condition
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit

pytestmark = [pytest.mark.kuadrant_only]

LIMIT = Limit(2, "10s")


@pytest.fixture(scope="module")
def rate_limit2(gateway, blame, cluster, label):
    """2nd RateLimitPolicy object allowing 2 requests per 10 seconds (a.k.a. '2rp10s')"""
    rlp = RateLimitPolicy.create_instance(cluster, blame("2rp10s"), gateway, labels={"testRun": label})
    rlp.add_limit("2rp10s", [LIMIT])
    return rlp


@pytest.fixture(scope="module", autouse=True)
def commit(request, rate_limit, rate_limit2):
    """Ensure RLPs are created"""
    for rlp in [rate_limit, rate_limit2]:
        if rlp is not None:
            request.addfinalizer(rlp.delete)
            rlp.commit()
            rlp.wait_for_accepted()

    rate_limit.wait_for_ready()

    # At this point the 'route2' has not been created yet so rate_limit2 is completely overridden by rate_limit
    assert rate_limit2.wait_until(
        has_condition("Enforced", "False", "Overridden")
    ), f"'2pr10s' RLP did not reach expected record status, instead it was: {rate_limit2.model.status.condition}"


def test_identical_hostnames_rlp_on_gw_and_route(client, rate_limit, rate_limit2):
    """
    Tests that Gateway-attached RateLimitPolicy is enforced on 'route2' if both 'route' and 'route2' declare
    identical hostname and there is another RateLimitPolicy already successfully enforced on 'route'.
    Setup:
        - Two HTTPRoutes declaring identical hostnames but different paths: '/anything/route1' and '/anything/route2'
        - '1rp10s' RateLimitPolicy enforced on the '/anything/route1' HTTPRoute
        - '2rp10s' RateLimitPolicy (created after '1pr10s' RateLimitPolicy) enforced on the Gateway
    Test:
        - Send requests via 'route' and assert that 429 is returned after one 200 OK
        - Send a request via 'route2' and assert that 429 is returned after two 200s
        - Delete the '1rp10s' RateLimitPolicy
        - Send a request via both routes
        - Assert that on both routes the 429s are returned after two 200s
    """
    # At this point route2 exists so the '2rp10s' RLP should not be overridden, should be partially enforced instead
    rate_limit2.wait_for_partial_enforced()

    # Access via 'route' is limited due to '1rp10s' RateLimitPolicy
    response = client.get("/anything/route1/get")
    assert response.status_code == 200
    response = client.get("/anything/route1/get")
    assert response.status_code == 429

    # Access via 'route2' is limited due to '2rp10s' Gateway RateLimitPolicy
    responses = client.get_many("/anything/route2/get", LIMIT.limit)
    responses.assert_all(status_code=200)
    response = client.get("/anything/route2/get")
    assert response.status_code == 429

    # Deletion of '1rp10s' RateLimitPolicy should make both routes rate-limited by '2pr10s' RLP.
    # '2pr10s' RLP should get fully enforced (was: partially enforced)
    rate_limit.delete()
    rate_limit2.wait_for_ready()

    # Wait for 15 seconds to make sure counter is reset
    sleep(15)

    responses = client.get_many("/anything/route1/get", LIMIT.limit)
    responses.assert_all(status_code=200)
    response = client.get("/anything/route1/get")
    assert response.status_code == 429

    responses = client.get_many("/anything/route2/get", LIMIT.limit)
    responses.assert_all(status_code=200)
    response = client.get("/anything/route2/get")
    assert response.status_code == 429

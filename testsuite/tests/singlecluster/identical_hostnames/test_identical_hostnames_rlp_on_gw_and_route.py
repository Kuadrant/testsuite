"""
Tests behavior of using one HTTPRoute declaring the same hostname as parent Gateway related to RateLimitPolicy.
https://github.com/Kuadrant/kuadrant-operator/blob/main/doc/rate-limiting.md#limitation-multiple-network-resources-with-identical-hostnames
(second topology mentioned there)
"""

import pytest

from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture(scope="class")
def rate_limit2(request, gateway, blame, cluster, label):
    """2nd RateLimitPolicy object allowing 1 request per 10 minutes (a.k.a. '1rp10m')"""
    rlp = RateLimitPolicy.create_instance(cluster, blame("2rp10m"), gateway, labels={"testRun": label})
    request.addfinalizer(rlp.delete)
    rlp.add_limit("1rp10m", [Limit(1, 600)])
    rlp.commit()
    rlp.wait_for_partial_enforced()
    return rlp


def test_identical_hostnames_rlp_on_gw_and_route_ignored(client, rate_limit, rate_limit2):
    """
    Tests that Gateway-attached RateLimitPolicy is ignored on 'route2' if both 'route' and 'route2' declare
    identical hostname and there is another RateLimitPolicy already successfully enforced on 'route'.
    Setup:
        - Two HTTPRoutes declaring identical hostnames but different paths: '/anything/route1' and '/anything/route2'
        - Empty RateLimitPolicy enforced on the '/anything/route1' HTTPRoute
        - '1rp10m' RateLimitPolicy (created after Empty RateLimitPolicy) enforced on the Gateway
    Test:
        - Send a request via 'route' and assert that no 429s (Too Many Requests) are returned
        - Send a request via 'route2' and assert that no 429s (Too Many Requests)are returned
        - Delete the Empty RateLimitPolicy
        - Send a request via both routes
        - Assert that on both routes the 429s are returned after single 200 (OK)
    """

    # Verify that the Empty RLP is still enforced despite '1rp10m' RLP being partially enforced now
    rate_limit.wait_for_ready()

    # Access via 'route' is not limited due to Empty RateLimitPolicy
    responses = client.get_many("/anything/route1/get", 2)
    responses.assert_all(status_code=200)

    # Access via 'route2' is limited due to '1rp10m' Gateway RateLimitPolicy (it is partially enforced)
    response = client.get("/anything/route2/get")
    assert response.status_code == 200
    responses = client.get_many("/anything/route2/get", 2)
    responses.assert_all(status_code=429)

    # Deletion of Empty RateLimitPolicy should make the '1rp10m' Gateway RateLimitPolicy fully enforced on both routes
    rate_limit.delete()
    rate_limit2.wait_for_ready()

    response = client.get("/anything/route1/get")
    assert response.status_code == 429

    response = client.get("/anything/route2/get")
    assert response.status_code == 429

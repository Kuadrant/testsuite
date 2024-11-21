"""
There used to be a limitation if using one HTTPRoute declaring the same hostname as parent Gateway related to RLP.
https://github.com/Kuadrant/kuadrant-operator/blob/3b8e313d552090c52d8aadca95f6952f42a03192/doc/rate-limiting.md#limitation-multiple-network-resources-with-identical-hostnames
(the first topology mentioned there)
This test validates that it has been properly fixed, i.e. both RateLimitPolicies (RLPs) are successfully enforced.
"""

from time import sleep
import pytest

from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit


pytestmark = [pytest.mark.kuadrant_only]

LIMIT = Limit(2, "10s")


@pytest.fixture(scope="module")
def rate_limit2(route2, blame, cluster, label):
    """2nd RateLimitPolicy allowing 2 requests per 10 seconds (a.k.a. '2rp10s' RateLimitPolicy)"""
    rlp = RateLimitPolicy.create_instance(cluster, blame("2rp10s"), route2, labels={"testRun": label})
    rlp.add_limit("2rp10m", [LIMIT])
    return rlp


@pytest.fixture(scope="module", autouse=True)
def commit(request, rate_limit, rate_limit2):
    """Ensure Authorizations are created"""
    for rlp in [rate_limit, rate_limit2]:
        if rlp is not None:
            request.addfinalizer(rlp.delete)
            rlp.commit()
            rlp.wait_for_ready()


def test_identical_hostnames_rlp_on_routes(client, rate_limit2):
    """
    Validates that 1st RateLimitPolicy is still enforced on 'route' declaring identical hostname as 'route2' if another
    RateLimitPolicy got successfully enforced on 'route2' in the interim.
    Setup:
        - Two HTTPRoutes declaring identical hostnames but different paths: '/anything/route1' and '/anything/route2'
        - '1rp10m' RateLimitPolicy enforced on the '/anything/route1' HTTPRoute
        - '2rp10m' RateLimitPolicy (created after '1rp10s' RateLimitPolicy) enforced on the '/anything/route2' HTTPRoute
    Test:
        - Send a request via 'route' and assert that no 429s (Too Many Requests) are returned
        - Send a request via 'route2' and assert that no 429s (Too Many Requests) are returned
        - Delete the '2rp10s' RateLimitPolicy
        - Send a request via both routes
        - Assert that 429 is returned after single 200 (OK) for route1
        - Assert that there are no 429s for 'route2'
    """
    # Access via 'route' is limited due to '1rp10s' RateLimitPolicy
    # despite it reporting being successfully enforced
    response = client.get("/anything/route1/get")
    assert response.status_code == 200
    response = client.get("/anything/route1/get")
    assert response.status_code == 429

    # Access via 'route2' is limited due to '2rp10s' RateLimitPolicy
    responses = client.get_many("/anything/route2/get", LIMIT.limit)
    responses.assert_all(status_code=200)
    response = client.get("/anything/route2/get")
    assert response.status_code == 429

    # Deletion of '2rp10m' RateLimitPolicy
    rate_limit2.delete()

    # Access via 'route' should now be still limited via '1rp10s' RateLimitPolicy
    # Wait for 15s to make sure the counter is reset
    sleep(15)
    response = client.get("/anything/route1/get")
    assert response.status_code == 200
    response = client.get("/anything/route1/get")
    assert response.status_code == 429

    # Access via 'route2' is now not limited at all
    responses = client.get_many("/anything/route2/get", LIMIT.limit + 1)
    responses.assert_all(status_code=200)

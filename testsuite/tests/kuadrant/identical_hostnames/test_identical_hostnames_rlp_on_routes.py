"""
Tests behavior of using one HTTPRoute declaring the same hostname as parent Gateway related to RateLimitPolicy.
https://github.com/Kuadrant/kuadrant-operator/blob/main/doc/rate-limiting.md#limitation-multiple-network-resources-with-identical-hostnames
(the first topology mentioned there)
"""

import pytest

from testsuite.policy.rate_limit_policy import RateLimitPolicy, Limit

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to 1st RateLimitPolicy allowing 1 request per 10 minutes (a.k.a. '1rp10m' RateLimitPolicy)"""
    rate_limit.add_limit("1rp10m", [Limit(1, 10)])
    return rate_limit


@pytest.fixture(scope="class")
def rate_limit2(request, route2, blame, openshift, label):
    """2nd RateLimitPolicy allowing 2 requests per 10 minutes (a.k.a. '2rp10m' RateLimitPolicy)"""
    rlp = RateLimitPolicy.create_instance(openshift, blame("2rp10m"), route2, labels={"testRun": label})
    request.addfinalizer(rlp.delete)
    rlp.add_limit("2rp10m", [Limit(2, 10)])
    rlp.commit()
    rlp.wait_for_ready()
    return rlp


def test_identical_hostnames_rlp_on_routes_ignored(client, rate_limit, rate_limit2, hostname):
    """
    Tests that 1st RateLimitPolicy gets ignored on 'route' declaring identical hostname as 'route2' when another
    RateLimitPolicy gets successfully enforced on 'route2'.
    Setup:
        - Two HTTPRoutes declaring identical hostnames but different paths: '/anything/route1' and '/anything/route2'
        - '1rp10m' RateLimitPolicy enforced on the '/anything/route1' HTTPRoute
        - '2rp10m' RateLimitPolicy (created after '1rp10m' RateLimitPolicy) enforced on the '/anything/route2' HTTPRoute
    Test:
        - Send a request via 'route' and assert that no 429s (Too Many Requests) are returned
        - Send a request via 'route2' and assert that no 429s (Too Many Requests)are returned
        - Delete the Empty RateLimitPolicy
        - Send a request via both routes
        - Assert that on both routes the 429s are returned after single 200 (OK)
    """

    # Verify that the '1rp10m' RLP is still enforced despite '2rp10m' RLP being enforced too now
    rate_limit.wait_for_ready()

    # Access via 'route' is not limited at all because '1rp10m' RateLimitPolicy is ignored
    # despite it reporting being successfully enforced
    responses = client.get_many("/anything/route1/get", 3)
    responses.assert_all(status_code=200)

    # Access via 'route2' is limited due to '2rp10m' RateLimitPolicy
    responses = client.get_many("/anything/route2/get", 2)
    responses.assert_all(status_code=200)
    # There might be more than two 200 OKs responses, might be due to '2rp10m' enforcement still being in progres
    with hostname.client(retry_codes={200}) as retry_client:
        response = retry_client.get("/anything/route2/get")
        assert response.status_code == 429

    # Deletion of '2rp10m' RateLimitPolicy should make '1rp10m' RateLimitPolicy effectively enforced.
    rate_limit2.delete()
    rate_limit.wait_for_ready()

    # Access via 'route' should now be limited via '1rp10m' RateLimitPolicy
    response = client.get("/anything/route1/get")
    assert response.status_code == 200
    # There might be more than two 200 OKs responses, might be due to '1rp10m' enforcement still being in progres
    with hostname.client(retry_codes={200}) as retry_client:
        response = retry_client.get("/anything/route1/get")
        assert response.status_code == 429

    # Access via 'route2' is now not limited at all
    responses = client.get_many("/anything/route2/get", 3)
    responses.assert_all(status_code=200)

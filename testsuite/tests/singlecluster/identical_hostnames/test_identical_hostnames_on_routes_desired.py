"""
Tests desired behavior of using two HTTPRoutes declaring the same hostname using both AuthPolicy and RateLimitPolicy.
https://github.com/Kuadrant/kuadrant-operator/blob/main/doc/auth.md#limitation-multiple-network-resources-with-identical-hostnames
https://github.com/Kuadrant/kuadrant-operator/blob/main/doc/rate-limiting.md#limitation-multiple-network-resources-with-identical-hostnames
(see the first topology mentioned in both links).
For AuthPolicy, the test should start passing once the policy-2 is enforced on route-b
For RateLimitPolicy (RLP) the test should start passing once the policy-1 is effectively enforced on route-a
"""

import pytest

from testsuite.policy.authorization.auth_policy import AuthPolicy
from testsuite.policy.rate_limit_policy import Limit, RateLimitPolicy

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture(scope="class")
def authorization2(request, route2, blame, openshift, label):
    """2nd Authorization object"""
    auth_policy = AuthPolicy.create_instance(openshift, blame("authz2"), route2, labels={"testRun": label})
    auth_policy.authorization.add_opa_policy("rego", "allow = false")
    request.addfinalizer(auth_policy.delete)
    auth_policy.commit()
    auth_policy.wait_for_accepted()
    return auth_policy


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to 1st RateLimitPolicy allowing 1 request per 10 minutes (a.k.a. '1rp10m' RateLimitPolicy)"""
    rate_limit.add_limit("1rp10m", [Limit(1, 10)])
    return rate_limit


@pytest.fixture(scope="class", autouse=True)
def rate_limit2(request, route2, blame, openshift, label):
    """2nd RateLimitPolicy allowing 2 requests per 10 minutes (a.k.a. '2rp10m' RateLimitPolicy)"""
    rlp = RateLimitPolicy.create_instance(openshift, blame("2rp10m"), route2, labels={"testRun": label})
    request.addfinalizer(rlp.delete)
    rlp.add_limit("2rp10m", [Limit(2, 10)])
    rlp.commit()
    rlp.wait_for_ready()
    return rlp


@pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/issues/431")
@pytest.mark.xfail(reason="Currently the 2nd AuthPolicy fails with: AuthScheme is not ready yet, see issue 431, Tier2")
def test_identical_hostnames_auth_on_routes_enforced(client, authorization2):
    """
    Tests that 2nd AuthPolicy is enforced on 'route2' declaring identical hostname as 'route' with another
    AuthPolicy already successfully enforced on 'route'.
    Setup:
        - Two HTTPRoutes declaring identical hostnames but different paths: '/anything/route1' and '/anything/route2'
        - Empty AuthPolicy enforced on the '/anything/route1' HTTPRoute
        - 2nd 'deny-all' AuthPolicy (created after Empty AuthPolicy) accepted on the '/anything/route2' HTTPRoute
    Test:
        - Assert that 'deny-all' AuthPolicy is enforced (expected to fail)
    """

    # 2nd 'deny-all' AuthPolicy should be enforced, this is expected to fail currently
    assert authorization2.wait_for_ready()

    # Access via route2 should be forbidden due to enforced 'deny-all' AuthPolicy, this is expected to fail currently
    response = client.get("/anything/route2/get")
    assert response.status_code == 403


@pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/issues/431")
@pytest.mark.xfail(reason="2nd RLP wins currently whereas 1st RLP should win to be consistent with AuthPolicy behavior")
def test_identical_hostnames_rlp_on_routes_1st_wins(client, rate_limit):
    """
    Tests that 1st RateLimitPolicy stays enforced on 'route' declaring identical hostname as 'route2' when another
    RateLimitPolicy gets successfully enforced on 'route2'.
    Setup:
        - Two HTTPRoutes declaring identical hostnames but different paths: '/anything/route1' and '/anything/route2'
        - '1rp10m' RateLimitPolicy enforced on the '/anything/route1' HTTPRoute
        - '2rp10m' RateLimitPolicy (created after '1rp10m' RateLimitPolicy) enforced on the '/anything/route2' HTTPRoute
    Test:
        - Assert that 1st '1rp10m' RateLimitPolicy is enforced
        - Send a request via 'route' and assert that 429s (Too Many Requests) are returned (this is expected to fail)
    """

    # Verify that the '1rp10m' RLP is still enforced despite '2rp10m' RLP being enforced too now
    rate_limit.wait_for_ready()

    # Access via 'route1' is limited by 1st '1rp10m' RLP hence the first request is 200 (OK)
    response = client.get("/anything/route1/get")
    assert response.status_code == 200

    # This is currently expected to fail because 1st '1rp10m' RLP is actually not enforced despite its status saying so
    response = client.get("/anything/route1/get")
    assert response.status_code == 429

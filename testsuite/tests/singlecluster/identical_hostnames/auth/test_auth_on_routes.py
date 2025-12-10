"""
There used to be a limitation if using two HTTPRoutes declaring the same hostname related to AuthPolicy:
https://github.com/Kuadrant/kuadrant-operator/blob/c8d083808daff46772254e223407c849b55020a7/doc/auth.md#limitation-multiple-network-resources-with-identical-hostnames
(the first topology mentioned there)
This test validates that it has been properly fixed, i.e. both AuthPolicies are fully and successfully enforced.
"""

import pytest

from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy

pytestmark = [pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def authorization2(route2, blame, cluster, label):
    """2nd 'deny-all' Authorization object"""
    auth_policy = AuthPolicy.create_instance(cluster, blame("authz2"), route2, labels={"testRun": label})
    auth_policy.authorization.add_opa_policy("rego", "allow = false")
    return auth_policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, authorization2):
    """Ensure Authorizations are created"""
    for auth in [authorization, authorization2]:
        if auth is not None:
            request.addfinalizer(auth.delete)
            auth.commit()
            auth.wait_for_ready()


def test_identical_hostnames_auth_on_routes(client, authorization):
    """
    Validate that 2nd AuthPolicy is fully enforced on 'route2' declaring identical hostname as 'route' when another
    AuthPolicy already successfully enforced on 'route'.
    Setup:
        - Two HTTPRoutes declaring identical hostnames but different paths: '/anything/route1' and '/anything/route2'
        - 'allow-all' AuthPolicy enforced on the '/anything/route1' HTTPRoute
        - 'deny-all' AuthPolicy (created after 'allow-all' AuthPolicy) enforced on the '/anything/route2' HTTPRoute
    Test:
        - Send a request via 'route' and assert that response status code is 200 OK
        - Send a request via 'route2' and assert that response status code is 403 Forbidden
        - Delete the 'allow-all' AuthPolicy
        - Send a request via both routes
        - Assert that access via 'route' is still 200 (OK), deletion of 'allow-all' Authpolicy should have no effect
        - Assert that access via 'route2' is still 403 (Forbidden)
    """

    response = client.get("/anything/route1/get")
    assert response.status_code == 200

    response = client.get("/anything/route2/get")
    assert response.status_code == 403

    # Deletion of 'allow-all' AuthPolicy
    authorization.delete()

    # Access via 'route' is still allowed because 'deny-all' AuthPolicy is not enforced on this route
    response = client.get("/anything/route1/get")
    assert response.status_code == 200

    # Access via 'route2' is still not allowed due to 'deny-all' AuthPolicy being enforced on 'route2'
    response = client.get("/anything/route2/get")
    assert response.status_code == 403

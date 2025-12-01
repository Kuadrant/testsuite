"""
There used to be a limitation if using one HTTPRoute declaring the same hostname as parent Gateway related to AuthPolicy
https://github.com/Kuadrant/kuadrant-operator/blob/c8d083808daff46772254e223407c849b55020a7/doc/auth.md#limitation-multiple-network-resources-with-identical-hostnames
(second topology mentioned there)
This test validates that it has been properly fixed, i.e. both AuthPolicies are fully and successfully enforced.
"""

import pytest

from testsuite.kuadrant.policy import has_condition
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy

pytestmark = [pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def authorization2(gateway, blame, cluster, label):
    """2nd 'deny-all' Authorization object"""
    auth_policy = AuthPolicy.create_instance(cluster, blame("authz2"), gateway, labels={"testRun": label})
    auth_policy.authorization.add_opa_policy("rego", "allow = false")
    return auth_policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, authorization2):
    """Ensure Authorizations are created"""
    for auth in [authorization, authorization2]:
        if auth is not None:
            request.addfinalizer(auth.delete)
            auth.commit()
            auth.wait_for_accepted()

    authorization.wait_for_ready()

    # At this point the 'route2' has not been created yet so authorization2 is completely overridden by authorization1
    assert authorization2.wait_until(has_condition("Enforced", "False", "Overridden")), (
        f"'deny-all' AuthPolicy did not reach expected record status, instead it was: "
        f"{authorization2.model.status.condition}"
    )


def test_identical_hostnames_auth_on_gw_and_route(client, authorization, authorization2):
    """
    Tests that Gateway-attached AuthPolicy affects on 'route2' even if both 'route' and 'route2' declare identical
    hostname and there is another AuthPolicy already successfully enforced on 'route'.
    Setup:
        - Two HTTPRoutes declaring identical hostnames but different paths: '/anything/route1' and '/anything/route2'
        - 'allow-all' AuthPolicy enforced on the '/anything/route1' HTTPRoute
        - 'deny-all' AuthPolicy (created after 'allow-all' AuthPolicy) enforced on the Gateway
    Test:
        - Send a request via 'route' and assert that response status code is 200 OK
        - Send a request via 'route2' and assert that response status code is 403 Forbidden
        - Delete the 'allow-all' AuthPolicy
        - Send a request via both routes
        - Assert that both response status codes are 403 (Forbidden)
    """

    # Verify that the GW-level 'deny-all' AuthPolicy is now only partially enforced ('route2' only). It is overridden
    # for 'route1' by HTTPRoute-level 'allow-all' AuthPolicy
    authorization2.wait_for_partial_enforced()

    # Access via 'route' is allowed due to 'allow-all' AuthPolicy
    response = client.get("/anything/route1/get")
    assert response.status_code == 200

    # 'deny-all' Gateway AuthPolicy affects route2
    response = client.get("/anything/route2/get")
    assert response.status_code == 403

    # Deletion of 'allow-all' AuthPolicy should make the 'deny-all' Gateway AuthPolicy enforced on both routes
    authorization.delete()
    authorization2.wait_for_ready()

    response = client.get("/anything/route1/get")
    assert response.status_code == 403

    response = client.get("/anything/route2/get")
    assert response.status_code == 403

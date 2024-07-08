"""
Tests behavior of using one HTTPRoute declaring the same hostname as parent Gateway related to AuthPolicy.
https://github.com/Kuadrant/kuadrant-operator/blob/main/doc/auth.md#limitation-multiple-network-resources-with-identical-hostnames
(second topology mentioned there)
"""

import pytest

from testsuite.policy.authorization.auth_policy import AuthPolicy

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture(scope="class", autouse=True)
def authorization2(request, gateway, blame, cluster, label):
    """2nd Authorization object"""
    auth_policy = AuthPolicy.create_instance(cluster, blame("authz2"), gateway, labels={"testRun": label})
    auth_policy.authorization.add_opa_policy("rego", "allow = false")
    request.addfinalizer(auth_policy.delete)
    auth_policy.commit()
    auth_policy.wait_for_ready()
    return auth_policy


def test_identical_hostnames_auth_on_gw_and_route_ignored(client, authorization, hostname):
    """
    Tests that Gateway-attached AuthPolicy is ignored on 'route2' if both 'route' and 'route2' declare
    identical hostname and there is another AuthPolicy already successfully enforced on 'route'.
    Setup:
        - Two HTTPRoutes declaring identical hostnames but different paths: '/anything/route1' and '/anything/route2'
        - Empty AuthPolicy enforced on the '/anything/route1' HTTPRoute
        - 'deny-all' AuthPolicy (created after Empty AuthPolicy) enforced on the Gateway
    Test:
        - Send a request via 'route' and assert that response status code is 200
        - Send a request via 'route2' and assert that response status code is 200
        - Delete the Empty AuthPolicy
        - Send a request via both routes
        - Assert that both response status codes are 403 (Forbidden)
    """

    # Verify that the Empty AuthPolicy is still enforced despite 'deny-all' AuthPolicy being enforced too now
    authorization.wait_for_ready()

    # Access via 'route' is allowed due to Empty AuthPolicy
    response = client.get("/anything/route1/get")
    assert response.status_code == 200

    # Despite 'deny-all' Gateway AuthPolicy reporting being successfully enforced
    # it is still allowed to access the resources via 'route2'
    response = client.get("/anything/route2/get")
    assert response.status_code == 200

    # Deletion of Empty AuthPolicy should make the 'deny-all' Gateway AuthPolicy effectively enforced on both routes.
    # It might take some time hence the use of retry client.
    authorization.delete()
    with hostname.client(retry_codes={200}) as retry_client:
        response = retry_client.get("/anything/route1/get")
        assert response.status_code == 403

    response = client.get("/anything/route2/get")
    assert response.status_code == 403

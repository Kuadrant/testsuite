"""
Tests desired behavior of using one HTTPRoute declaring the same hostname as parent Gateway related to AuthPolicy.
https://github.com/Kuadrant/kuadrant-operator/blob/main/doc/auth.md#limitation-multiple-network-resources-with-identical-hostnames
(see second topology mentioned there). This test should start passing once the policy-2 affects the route-b which is
considered to be desired behavior.
"""

import pytest

from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture(scope="class", autouse=True)
def authorization2(request, gateway, blame, openshift, label):
    """2nd 'deny-all' Authorization object"""
    auth_policy = AuthPolicy.create_instance(openshift, blame("authz2"), gateway, labels={"testRun": label})
    auth_policy.authorization.add_opa_policy("rego", "allow = false")
    request.addfinalizer(auth_policy.delete)
    auth_policy.commit()
    auth_policy.wait_for_ready()
    return auth_policy


@pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/issues/431")
@pytest.mark.xfail(
    reason="Currently the Gateway-attached Policy is ignored so 200 (OK) is returned instead of 403 (Forbidden)"
)
def test_identical_hostnames_auth_on_gw_and_route_enforced(client, authorization):
    """
    Tests that Gateway-attached AuthPolicy is successfully enforced on 'route2' even if both 'route' and 'route2'
    declare identical hostname and there is another AuthPolicy already successfully enforced on 'route'.
    Setup:
        - Two HTTPRoutes declaring identical hostnames but different paths: '/anything/route1' and '/anything/route2'
        - Empty AuthPolicy enforced on the '/anything/route1' HTTPRoute
        - 'deny-all' AuthPolicy (created after Empty AuthPolicy) enforced on the Gateway
    Test:
        - Send a request via 'route' and assert that response status code is 200
        - Send a request via 'route2' and assert that response status code is 403 (it is expected to fail)
    """

    # Verify that the Empty AuthPolicy is still enforced despite 'deny-all' AuthPolicy being enforced too now
    authorization.wait_for_ready()

    # Access via 'route' is allowed due to Empty AuthPolicy
    response = client.get("/anything/route1/get")
    assert response.status_code == 200

    # Access via 'route2' should be forbidden due to 'deny-all' Gateway-attached AuthPolicy
    # However, this is currently expected to fail
    response = client.get("/anything/route2/get")
    assert response.status_code == 403

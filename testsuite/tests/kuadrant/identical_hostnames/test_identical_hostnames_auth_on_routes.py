"""
Tests behavior of using two HTTPRoutes declaring the same hostname related to AuthPolicy.
https://github.com/Kuadrant/kuadrant-operator/blob/main/doc/auth.md#limitation-multiple-network-resources-with-identical-hostnames
(the first topology mentioned there)
"""

import pytest

from testsuite.policy import has_condition
from testsuite.policy.authorization.auth_policy import AuthPolicy

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


def test_identical_hostnames_auth_on_routes_rejected(client, authorization, authorization2):
    """
    Tests that 2nd AuthPolicy is rejected on 'route2' declaring identical hostname as 'route' with another
    AuthPolicy already successfully enforced on 'route'.
    Setup:
        - Two HTTPRoutes declaring identical hostnames but different paths: '/anything/route1' and '/anything/route2'
        - Empty AuthPolicy enforced on the '/anything/route1' HTTPRoute
        - 'deny-all' AuthPolicy (created after Empty AuthPolicy) accepted on the '/anything/route2' HTTPRoute
    Test:
        - Assert that 'deny-all' AuthPolicy reports an error
        - Send a request via 'route' and assert that response status code is 200
        - Send a request via 'route2' and assert that response status code is 200
        - Delete the Empty AuthPolicy
        - Change 'deny-all' AuthPolicy to trigger its reconciliation
        - Send a request via both routes
        - Assert that access via 'route' is 200 (OK)
        - Assert that access via 'route2 is 403 (Forbidden)
    """
    assert authorization2.wait_until(
        has_condition(
            "Enforced",
            "False",
            "Unknown",
            "AuthPolicy has encountered some issues: AuthScheme is not ready yet",
        ),
        timelimit=20,
    ), (
        f"AuthPolicy did not reach expected status (Enforced False), "
        f"instead it was: {authorization2.refresh().model.status.conditions}"
    )

    response = client.get("/anything/route1/get")
    assert response.status_code == 200

    response = client.get("/anything/route2/get")
    assert response.status_code == 200

    # Deletion of Empty AuthPolicy should allow for 'deny-all' AuthPolicy to be enforced successfully.
    authorization.delete()

    # 2nd AuthPolicy only recovers from the "AuthScheme is not ready yet" error if reconciliation is explicitly
    # triggered, e.g. by changing the AuthPolicy CR content (changing AllValues to True in this particular case)
    # Reported as bug https://github.com/Kuadrant/kuadrant-operator/issues/702
    authorization2.authorization.add_opa_policy("rego", "allow = false", True)
    authorization2.refresh()
    authorization2.wait_for_ready()

    # Access via 'route' is still allowed
    response = client.get("/anything/route1/get")
    assert response.status_code == 200

    # Access via 'route2' is now not allowed due to 'deny-all' AuthPolicy being enforced on 'route2'
    response = client.get("/anything/route2/get")
    assert response.status_code == 403

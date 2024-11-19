"""
Tests behavior of using two HTTPRoutes declaring the same hostname related to AuthPolicy.
https://github.com/Kuadrant/kuadrant-operator/blob/main/doc/auth.md#limitation-multiple-network-resources-with-identical-hostnames
(the first topology mentioned there)
"""

import pytest

from testsuite.kuadrant.policy import has_condition
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def authorization2(request, route2, blame, cluster, label):
    """2nd Authorization object"""
    auth = AuthPolicy.create_instance(cluster, blame("authz2"), route2, labels={"testRun": label})
    auth.authorization.add_opa_policy("rego", "allow = false")
    return auth


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
    response = client.get("/anything/route1/get")
    assert response.status_code == 200

    response = client.get("/anything/route2/get")
    assert response.status_code == 403

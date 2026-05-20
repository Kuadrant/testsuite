"""Test auth policies collisions when attached to the same target"""

import pytest

from testsuite.httpx.auth import HeaderApiKeyAuth
from testsuite.kuadrant.policy import has_condition
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy

pytestmark = [pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def api_key(create_api_key, module_label):
    """Creates API key Secret."""
    return create_api_key("api-key", module_label, "api_key_value")


@pytest.fixture(scope="module")
def target(request):
    """Returns the test target(gateway or route)"""
    return request.getfixturevalue(request.param)


@pytest.fixture(scope="module")
def authorization(
    request, gateway, route, cluster, blame, target, label, oidc_provider
):  # pylint: disable=unused-argument
    """Create an AuthPolicy with either gateway or route as target reference"""
    auth = AuthPolicy.create_instance(cluster, blame("fp"), target, labels={"testRun": label})
    auth.identity.add_oidc("first", oidc_provider.well_known["issuer"])
    return auth


@pytest.fixture(scope="module")
def authorization2(request, cluster, blame, target, label, api_key):  # pylint: disable=unused-argument
    """Create a second AuthPolicy with the same target as the first AuthPolicy"""
    auth = AuthPolicy.create_instance(cluster, blame("sp"), target, labels={"testRun": label})
    auth.identity.add_api_key("second", selector=api_key.selector)
    return auth


@pytest.fixture(scope="module")
def auth2(api_key):
    """API key Auth"""
    return HeaderApiKeyAuth(api_key)


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, authorization2):
    """Commits both AuthPolicies after the target is created"""
    for policy in [authorization, authorization2]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_ready()


@pytest.mark.parametrize("target", ["gateway", "route"], indirect=True)
def test_collision_auth_policy(client, authorization, auth, auth2):
    """Test first policy is being overridden when another policy with the same target is created."""
    assert authorization.wait_until(has_condition("Enforced", "False", "Overridden", "AuthPolicy is overridden"))
    assert client.get("/get", auth=auth).status_code == 401
    assert client.get("/get", auth=auth2).status_code == 200

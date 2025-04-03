"""Test auth policies collisions when attached to the same target"""

import pytest

from testsuite.httpx.auth import HeaderApiKeyAuth
from testsuite.kuadrant.policy import has_condition
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy


@pytest.fixture(scope="module")
def api_key(create_api_key, module_label):
    """Creates API key Secret."""
    return create_api_key("api-key", module_label, "api_key_value")


# pylint: disable = unused-argument
@pytest.fixture(scope="module")
def authorization(request, cluster, blame, module_label, route, label, oidc_provider):
    """Create a RateLimitPolicy with a basic limit with target coming from test parameter"""
    target_ref = request.getfixturevalue(getattr(request, "param", "route"))

    auth = AuthPolicy.create_instance(cluster, blame("fp"), target_ref, labels={"testRun": label})
    auth.identity.add_oidc("first", oidc_provider.well_known["issuer"])
    return auth


@pytest.fixture(scope="module")
def authorization2(request, cluster, blame, module_label, route, label, api_key):
    """Create a RateLimitPolicy with a basic limit with target coming from test parameter"""
    target_ref = request.getfixturevalue(getattr(request, "param", "route"))

    auth = AuthPolicy.create_instance(cluster, blame("sp"), target_ref, labels={"testRun": label})
    auth.identity.add_api_key("second", selector=api_key.selector)
    return auth


@pytest.fixture(scope="module")
def auth2(api_key):
    """API key Auth"""
    return HeaderApiKeyAuth(api_key)


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, authorization2):
    """Commits AuthPolicy after the target is created"""
    for policy in [authorization, authorization2]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_ready()


@pytest.mark.parametrize("authorization", ["gateway", "route"], indirect=True)
def test_collision_auth_policy(client, authorization, authorization2, auth, auth2):
    """Test first policy is being overridden when another policy with the same target is created."""
    assert authorization.wait_until(has_condition("Enforced", "False", "Overridden", "AuthPolicy is overridden"))
    assert client.get("/get", auth=auth).status_code == 401
    assert client.get("/get", auth=auth2).status_code == 200

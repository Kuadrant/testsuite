"""Conftest for defaults merge strategy tests for AuthPolicies"""

import pytest

from testsuite.httpx.auth import HeaderApiKeyAuth, HttpxOidcClientAuth
from testsuite.kuadrant.policy import Strategy
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy


@pytest.fixture(scope="module")
def user_label(blame):
    """Creates a label prefixed as user"""
    return blame("user")


@pytest.fixture(scope="module")
def admin_label(blame):
    """Creates a label prefixed as admin"""
    return blame("admin")


@pytest.fixture(scope="module")
def user_api_key(create_api_key, user_label):
    """Creates API key Secret for a user"""
    annotations = {"kuadrant.io/groups": "users"}
    secret = create_api_key("api-key", user_label, "api_key_value", annotations=annotations)
    return secret


@pytest.fixture(scope="module")
def admin_api_key(create_api_key, admin_label):
    """Creates API key Secret for an admin"""
    annotations = {"kuadrant.io/groups": "admins"}
    secret = create_api_key("admin-api-key", admin_label, "admin_api_key_value", annotations=annotations)
    return secret


@pytest.fixture(scope="module")
def user_auth(user_api_key):
    """Valid API Key Auth for user"""
    return HeaderApiKeyAuth(user_api_key)


@pytest.fixture(scope="module")
def admin_auth(admin_api_key):
    """Valid API Key Auth for admin"""
    return HeaderApiKeyAuth(admin_api_key)


@pytest.fixture()
def auth(oidc_provider):
    """Returns Authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def global_authorization(request, cluster, blame, admin_label, admin_api_key):
    """
    Create an AuthPolicy with authentication for an admin with same target as one default.
    Also adds authorization for only admins.
    """
    target_ref = request.getfixturevalue(getattr(request, "param", "gateway"))

    auth_policy = AuthPolicy.create_instance(cluster, blame("dmp"), target_ref, labels={"testRun": admin_label})
    auth_policy.defaults.identity.add_api_key("api-key", selector=admin_api_key.selector)
    auth_policy.defaults.authorization.add_opa_policy(
        "group-allowed",
        """
        groups := split(object.get(input.auth.identity.metadata.annotations, "kuadrant.io/groups", ""), ",")
                allow { groups[_] != "" }""",
    )
    auth_policy.defaults.strategy(Strategy.MERGE)
    return auth_policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, global_authorization, authorization):  # pylint: disable=unused-argument
    """Commits AuthPolicy after the HTTPRoute is created"""
    for policy in [global_authorization, authorization]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_accepted()
        policy.wait_for_ready()

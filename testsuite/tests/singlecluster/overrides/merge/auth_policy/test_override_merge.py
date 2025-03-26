"""Test override overriding another policy aimed at the same Gateway Listener."""

import pytest

from testsuite.kuadrant.policy import has_condition
from testsuite.kuadrant.policy.authorization import Credentials
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kuadrant.policy.rate_limit import Strategy

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def authorization(cluster, blame, admin_api_key, module_label, route):
    """Create an AuthPolicy with authentication for a simple user with same target as one default."""
    auth_policy = AuthPolicy.create_instance(cluster, blame("sp"), route, labels={"testRun": module_label})
    auth_policy.identity.add_api_key("admins", selector=admin_api_key.selector)
    return auth_policy


@pytest.fixture(scope="module")
def override_auth_policy(cluster, blame, module_label, route, user_api_key):
    """
    Create an AuthPolicy with authentication for an admin with same target as one default.
    Also adds authorization for only admins.
    """

    auth_policy = AuthPolicy.create_instance(cluster, blame("omp"), route, labels={"testRun": module_label})
    auth_policy.overrides.identity.add_api_key("user-authorization-header", selector=user_api_key.selector)
    auth_policy.overrides.identity.add_api_key(
        "user-custom-header", selector=user_api_key.selector, credentials=Credentials("customHeader", "X-API-Key")
    )
    auth_policy.overrides.identity.add_api_key(
        "user-query-string-param", selector=user_api_key.selector, credentials=Credentials("queryString", "api_key")
    )
    auth_policy.overrides.identity.add_api_key(
        "members-cookie", selector=user_api_key.selector, credentials=Credentials("cookie", "APIKEY")
    )
    auth_policy.overrides.strategy(Strategy.MERGE)
    return auth_policy


@pytest.fixture(scope="function", autouse=True)
def commit(request, route, authorization, override_auth_policy):  # pylint: disable=unused-argument
    """Commits AuthPolicy after the HTTPRoute is created"""
    for policy in [override_auth_policy, authorization]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_accepted()


@pytest.mark.parametrize("authorization", ["gateway", "route"], indirect=True)
def test_override_merge(client, override_auth_policy, authorization, user_auth, admin_auth):
    """Test AuthPolicy with an override and merge strategy overriding only a part of a new policy."""
    assert override_auth_policy.wait_until(
        has_condition("Enforced", "True", "Enforced", "AuthPolicy has been successfully enforced")
    )
    assert authorization.wait_until(
        has_condition("Enforced", "True", "Enforced", "AuthPolicy has been successfully enforced")
    )

    assert client.get("/get").status_code == 401  # none of the policies allow anonymous authentication.
    assert client.get("/get", auth=user_auth).status_code == 200  # user authentication with api key
    assert (
            client.get("/get", headers={"X-API-KEY": user_auth.api_key}).status_code == 200
    )  # user authentication with header.
    assert (
            client.get("/get", params={"api_key": user_auth.api_key}).status_code == 200
    )  # user authentication with query string param.
    assert (
            client.get("/get", cookies={"APIKEY": user_auth.api_key}).status_code == 200
    )  # user authentication with cookie.
    assert client.get("/get", auth=admin_auth).status_code == 200  # admin authentication with api key.

    assert (
            client.get("/get", headers={"X-API-KEY": admin_auth.api_key}).status_code == 401
    )  # admin authentication with header should not work
    assert (
            client.get("/get", params={"api_key": admin_auth.api_key}).status_code == 401
    )  # admin authentication with query string param should not work.
    assert (
            client.get("/get", cookies={"APIKEY": admin_auth.api_key}).status_code == 401
    )  # admin authentication with cookie should not work.

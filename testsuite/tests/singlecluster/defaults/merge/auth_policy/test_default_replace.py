"""Test gateway level default merging being partially overriden by another policy."""

import pytest

from testsuite.kuadrant.policy import has_condition

pytestmark = [pytest.mark.defaults_overrides, pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def authorization(authorization, user_api_key):
    """Create an AuthPolicy with authentication with the same name as in the policy attached on the gateway"""
    authorization.identity.add_api_key("api-key", selector=user_api_key.selector)
    return authorization


def test_default_replace(client, global_authorization, user_auth, admin_auth):
    """
    Test Gateway policy being partially overridden when another policy is attached to route with the same name
    """
    assert global_authorization.wait_until(
        has_condition("Enforced", "True", "Enforced", "AuthPolicy has been partially enforced")
    )

    anon_auth_resp = client.get("/get")
    assert anon_auth_resp is not None
    assert anon_auth_resp.status_code == 401  # none of the policies allow anonymous authentication.

    user_auth_res = client.get("/get", auth=user_auth)
    assert user_auth_res is not None
    assert user_auth_res.status_code == 200  # user authentication with api key.

    admin_auth_res = client.get("/get", auth=admin_auth)  # admin authentication is being overridden.
    assert admin_auth_res is not None
    assert admin_auth_res.status_code == 401

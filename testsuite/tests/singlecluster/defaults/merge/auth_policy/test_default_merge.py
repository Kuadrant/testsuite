"""Test gateway level default merging not being overridden by another policy."""

import pytest

from testsuite.kuadrant.policy import has_condition

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(authorization, user_api_key):
    """Create an AuthPolicy with authentication for a simple user with same target as one default"""
    authorization.identity.add_api_key("second-api-key", selector=user_api_key.selector)
    return authorization


def test_default_merge(client, authorization, global_authorization, user_auth, admin_auth):
    """Both policies are enforced and not being overridden"""
    assert global_authorization.wait_until(
        has_condition("Enforced", "True", "Enforced", "AuthPolicy has been successfully enforced")
    )
    assert authorization.wait_until(
        has_condition("Enforced", "True", "Enforced", "AuthPolicy has been successfully enforced")
    )

    anon_auth_resp = client.get("/get")
    assert anon_auth_resp is not None
    assert anon_auth_resp.status_code == 401  # none of the policies allow anonymous authentication.

    user_auth_res = client.get("/get", auth=user_auth)
    assert user_auth_res is not None
    assert user_auth_res.status_code == 200  # user authentication with api key.

    admin_auth_res = client.get("/get", auth=admin_auth)  # admin authentication with api key.
    assert admin_auth_res is not None
    assert admin_auth_res.status_code == 200

"""Test gateway level default merging being partially overriden by another policy."""

import pytest

from testsuite.kuadrant.policy import has_condition
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(cluster, blame, user_api_key, module_label, route):
    """Create an AuthPolicy with authentication with the same name as in the policy attached on the gateway"""
    auth_policy = AuthPolicy.create_instance(cluster, blame("sp"), route, labels={"testRun": module_label})
    auth_policy.identity.add_api_key("api-key", selector=user_api_key.selector)
    return auth_policy


def test_default_replace(
    client, authorization, global_authorization, user_auth, admin_auth
):  # pylint: disable=unused-argument
    """
    Test Gateway policy being partially overridden when another policy is attached to route with the same name
    """
    assert global_authorization.wait_until(
        has_condition("Enforced", "True", "Enforced", "AuthPolicy has been partially enforced")
    )

    assert client.get("/get").status_code == 401  # none of the policies allow anonymous authentication.
    assert client.get("/get", auth=user_auth).status_code == 200  # user authentication works as expected.
    assert client.get("/get", auth=admin_auth).status_code == 401  # admin authentication is being overridden.

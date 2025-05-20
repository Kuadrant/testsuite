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
    auth_policy.identity.add_api_key("users", selector=admin_api_key.selector)
    return auth_policy


def test_override_merge(client, global_authorization, authorization, user_auth, admin_auth, auth):
    """Test AuthPolicy with an override and merge strategy overriding only a part of a new policy."""
    assert global_authorization.wait_until(
        has_condition("Enforced", "True", "Enforced", "AuthPolicy has been successfully enforced")
    )
    assert authorization.wait_until(
        has_condition("Enforced", "True", "Enforced", "AuthPolicy has been successfully enforced")
    )

    assert client.get("/get").status_code == 401  # none of the policies allow anonymous authentication.
    assert client.get("/get", auth=admin_auth).status_code == 200  # admin api key authentication works.
    assert client.get("/get", auth=user_auth).status_code == 401  # admin api key is overridden.
    assert client.get("/get", auth=auth).status_code == 200  # oidc authentication works.

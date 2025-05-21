"""Test merging defaults policies on gateway with policies on route with partial override."""

import pytest

from testsuite.kuadrant.policy import has_condition
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def authorization(cluster, blame, module_label, route, user_api_key):
    """Create an AuthPolicy with authentication for a simple user with same target as one default."""
    auth_policy = AuthPolicy.create_instance(cluster, blame("sp"), route, labels={"testRun": module_label})
    auth_policy.identity.add_api_key("api-key", selector=user_api_key.selector)
    return auth_policy


@pytest.mark.parametrize("target", ["gateway", "route"], indirect=True)
def test_override_replace(client, authorization, global_authorization, auth, admin_auth):
    """Test AuthPolicy with an override and merge strategy overriding only a part of a new policy."""
    assert authorization.wait_until(
        has_condition(
            "Enforced",
            "False",
            "Overridden",
            "AuthPolicy is overridden by " f"[{global_authorization.namespace()}/{global_authorization.name()}]",
        )
    )

    assert client.get("/get").status_code == 401  # none of the policies allow anonymous authentication.
    assert client.get("/get", auth=auth).status_code == 401  # user authentication is overridden by global.
    assert client.get("/get", auth=admin_auth).status_code == 200  # admin authentication is working.

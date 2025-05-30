"""Test merging defaults policies on gateway with policies on route with partial override."""

import pytest

from testsuite.kuadrant.policy import has_condition

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def authorization(authorization, user_api_key, route):
    """Create an AuthPolicy with authentication for a simple user with same target as one default."""
    authorization.identity.add_api_key("api-key", selector=user_api_key.selector)
    return authorization


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

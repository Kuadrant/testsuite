"""Test merging defaults policies on gateway with policies on route without override."""

import pytest

from testsuite.kuadrant.policy import has_condition

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def authorization(authorization, user_api_key, route):
    """Create an AuthPolicy with authentication for a simple user with same target as one default."""
    authorization.identity.add_api_key("second-api-key", selector=user_api_key.selector)
    return authorization


def test_override_merge(
    client, global_authorization, authorization, user_auth, admin_auth, auth
):  # pylint: disable=unused-argument
    """Test AuthPolicy with an override and merge strategy overriding only a part of a new policy."""
    assert global_authorization.wait_until(
        has_condition("Enforced", "True", "Enforced", "AuthPolicy has been successfully enforced")
    )
    assert authorization.wait_until(
        has_condition("Enforced", "True", "Enforced", "AuthPolicy has been successfully enforced")
    )

    assert client.get("/get").status_code == 401  # none of the policies allow anonymous authentication.
    assert client.get("/get", auth=admin_auth).status_code == 200  # admin api key authentication works.
    assert client.get("/get", auth=user_auth).status_code == 200  # user api key authentication works.

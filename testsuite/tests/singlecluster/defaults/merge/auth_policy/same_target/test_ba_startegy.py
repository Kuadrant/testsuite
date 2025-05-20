"""Test defaults policy aimed at the same resource uses the oldest policy."""

import pytest

from testsuite.kuadrant.policy import has_condition

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino]


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, authorization, global_authorization):  # pylint: disable=unused-argument
    """Commits AuthPolicy after the HTTPRoute is created"""
    for policy in [global_authorization, authorization]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_accepted()


@pytest.mark.parametrize("target", ["gateway", "route"], indirect=True)
def test_multiple_policies_merge_default_ba(client, global_authorization, user_auth, admin_auth):
    """Test AuthPolicy with merge defaults being ignored due to age"""
    assert global_authorization.wait_until(
        has_condition("Enforced", "True", "Enforced", "AuthPolicy has been partially enforced")
    )

    assert client.get("/get").status_code == 401  # anonymous authentication is not allowed.
    assert (
        client.get("/get", auth=user_auth).status_code == 403
    )  # user is authenticated, but it is forbidden in the authorization policy.
    assert (
        client.get("/get", auth=admin_auth).status_code == 401
    )  # admin is not authenticated, since the policy is ignored.

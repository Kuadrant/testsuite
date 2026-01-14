"""Test defaults policy aimed at the same resource uses the oldest policy."""

import pytest

from testsuite.kuadrant.policy import has_condition

pytestmark = [pytest.mark.defaults_overrides, pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, authorization, global_authorization):  # pylint: disable=unused-argument
    """Commits AuthPolicy after the HTTPRoute is created"""
    for policy in [global_authorization, authorization]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_accepted()
        policy.wait_for_ready()


@pytest.mark.parametrize(
    "authorization, global_authorization",
    [("gateway", "gateway"), ("route", "route")],
    indirect=True,
)
def test_multiple_policies_merge_default_ba(client, global_authorization, user_auth, admin_auth):
    """Test AuthPolicy with merge defaults being ignored due to age"""
    assert global_authorization.wait_until(
        has_condition("Enforced", "True", "Enforced", "AuthPolicy has been partially enforced")
    )

    anon_auth_resp = client.get("/get")
    assert anon_auth_resp is not None
    assert anon_auth_resp.status_code == 401  # anonymous authentication is not allowed.

    user_auth_res = client.get("/get", auth=user_auth)
    assert user_auth_res is not None
    assert user_auth_res.status_code == 200  # user is authenticated and authorized.

    admin_auth_res = client.get("/get", auth=admin_auth)  # admin is not authenticated, since the policy is ignored.
    assert admin_auth_res is not None
    assert admin_auth_res.status_code == 401

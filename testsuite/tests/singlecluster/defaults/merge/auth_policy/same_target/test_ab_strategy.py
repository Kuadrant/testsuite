"""Test defaults policy aimed at the same resource uses the oldest policy."""

import pytest

from testsuite.kuadrant.policy import has_condition

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino]


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, authorization, global_authorization):  # pylint: disable=unused-argument
    """Commits AuthPolicy after the HTTPRoute is created"""
    for policy in [authorization, global_authorization]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_accepted()


@pytest.mark.parametrize("target", ["gateway", "route"], indirect=True)
def test_multiple_policies_merge_default_ab(client, authorization, global_authorization, user_auth, admin_auth):
    """Test AuthPolicy with merge defaults being ignored due to age"""
    assert authorization.wait_until(
        has_condition(
            "Enforced",
            "False",
            "Overridden",
            "AuthPolicy is overridden by " f"[{global_authorization.namespace()}/{global_authorization.name()}]",
        )
    )

    assert client.get("/get").status_code == 401  # anonymous authentication is not allowed.
    assert client.get("/get", auth=user_auth).status_code == 401  # user authentication is overridden.
    assert client.get("/get", auth=admin_auth).status_code == 200  # admin authentication is allowed.

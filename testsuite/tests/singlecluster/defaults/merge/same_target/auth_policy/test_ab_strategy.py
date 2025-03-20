"""Test defaults policy aimed at the same resource uses the oldest policy."""

import pytest

from testsuite.kuadrant.policy import has_condition

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino]


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, authorization, default_merge_authorization):  # pylint: disable=unused-argument
    """Commits AuthPolicy after the HTTPRoute is created"""
    for policy in [authorization, default_merge_authorization]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_accepted()


def test_multiple_policies_merge_default_ab(client, authorization, default_merge_authorization, auth, merge_auth):
    """Test AuthPolicy with merge defaults being ignored due to age"""
    assert authorization.wait_until(
        has_condition(
            "Enforced",
            "False",
            "Overridden",
            "AuthPolicy is overridden by "
            f"[{default_merge_authorization.namespace()}/{default_merge_authorization.name()}]",
        )
    )

    assert client.get("/get").status_code == 200  # anonymous is accepted from authorization.
    assert client.get("/get", auth=auth).status_code == 200  # auth is accepted from authorization.
    assert (
        client.get("/get", auth=merge_auth).status_code == 200
    )  # merge auth is ignored, since it is being overridden.

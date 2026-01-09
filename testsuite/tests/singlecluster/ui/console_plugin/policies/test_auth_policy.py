"""Verifies that an AuthPolicy can be created, listed, and deleted via the console plugin UI"""

import pytest
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.page_objects.policies.auth_policy import AuthListPage, AuthNewPageYaml

pytestmark = [pytest.mark.ui]


def test_auth_policy_ui(request, navigator, cluster, blame, gateway, client):
    """Creates an AuthPolicy via the UI, verifies it appears, then deletes it via the UI"""

    # Prepare AuthPolicy policy data
    policy = AuthPolicy.create_instance(cluster, blame("authz"), gateway)
    policy.authorization.add_opa_policy("denyAll", "allow = false")

    # Register finalizer to ensure cleanup via API if UI fails
    request.addfinalizer(policy.delete)

    # Navigate to AuthPolicy creation page and create policy via editor
    new_page = navigator.navigate(AuthNewPageYaml)
    assert new_page.page_displayed(), "AuthPolicy creation page did not load"
    new_page.create(policy)

    # Verify AuthPolicy appears in the list
    list_page = navigator.navigate(AuthListPage)
    assert list_page.page_displayed(), "AuthPolicy list page did not load"
    policy_name = policy.model.metadata.name
    assert list_page.is_policy_listed(policy_name), f"AuthPolicy '{policy_name}' not found in list"

    # Verify AuthPolicy created via UI enforces as expected
    response = client.get("/get")
    assert response.status_code == 403

    # Delete AuthPolicy via UI
    list_page.delete(policy_name)

    # Verify AuthPolicy is deleted from the list
    assert not list_page.is_policy_listed(policy_name), f"AuthPolicy '{policy_name}' was not deleted"

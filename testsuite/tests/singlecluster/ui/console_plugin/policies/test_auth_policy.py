"""Verifies that an AuthPolicy can be created, listed, and deleted via the console plugin UI"""

import pytest
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.page_objects.policies.auth_policy import AuthListPage, AuthNewPage

pytestmark = [pytest.mark.ui]


def test_auth_policy_ui(request, navigator, cluster, blame, gateway):
    """Creates an AuthPolicy via the UI, verifies it appears, then deletes it via the UI"""

    # Prepare AuthPolicy policy data
    policy = AuthPolicy.create_instance(cluster, blame("authz"), gateway)
    policy.authorization.add_opa_policy("denyAll", "allow = false")

    # Register finalizer to ensure cleanup via API if UI fails
    request.addfinalizer(policy.delete)

    # Navigate to AuthPolicy creation page and create policy via editor
    new_page = navigator.navigate(AuthNewPage)
    new_page.create(policy)

    # Verify AuthPolicy appears in the list
    list_page = navigator.navigate(AuthListPage)
    policy_name = policy.model.metadata.name
    assert list_page.get_policy(policy_name), f"AuthPolicy '{policy_name}' not found in list"

    # Delete AuthPolicy via UI
    list_page.delete(policy_name)

    # Verify AuthPolicy is deleted from the list
    assert not list_page.has_policy(policy_name), f"AuthPolicy '{policy_name}' was not deleted"

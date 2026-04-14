"""Verifies that an OIDCPolicy can be created, listed, and deleted via the console plugin UI"""

import pytest

from testsuite.kuadrant.extensions.oidc_policy import OIDCPolicy, Provider
from testsuite.page_objects.policies.oidc_policy import OIDCPolicyNewPageYaml, OIDCPolicyListPage
from testsuite.page_objects.policies.auth_policy import AuthListPage

pytestmark = [pytest.mark.ui]


@pytest.mark.min_ocp_version((4, 20))
def test_oidc_policy_ui(request, navigator, cluster, blame, gateway):
    """Creates an OIDCPolicy via the UI, verifies it appears, then deletes it via the UI

    Also verifies 2 child AuthPolicies (main + callback) are auto-created and deleted

    Note: this test does not verify enforcement. OIDCPolicy requires OIDC provider setup to enforce.
    Enforcement is already tested in functional tests.
    """

    # Prepare OIDCPolicy with minimal provider config
    provider = Provider(
        issuerURL="https://example.com", clientID="test-client-id", redirectURI="https://example.com/callback"
    )
    policy = OIDCPolicy.create_instance(cluster, blame("oidc"), gateway, provider)

    # Register finalizer to ensure cleanup via API if UI fails
    request.addfinalizer(policy.delete)

    # Navigate to OIDCPolicy creation page and create policy via editor
    new_page = navigator.navigate(OIDCPolicyNewPageYaml)
    assert new_page.page_displayed(), "OIDCPolicy creation page did not load"
    new_page.create(policy)

    # Verify OIDCPolicy appears in the list
    oidc_list = navigator.navigate(OIDCPolicyListPage)
    assert oidc_list.page_displayed(), "OIDCPolicy list page did not load"
    policy_name = policy.model.metadata.name
    assert oidc_list.is_policy_listed(policy_name), f"OIDCPolicy '{policy_name}' not found in list"

    # Verify 2 child AuthPolicies were automatically created
    auth_list = navigator.navigate(AuthListPage)
    assert auth_list.page_displayed(), "AuthPolicy list page did not load"
    assert auth_list.is_policy_listed(
        policy_name
    ), f"Main AuthPolicy '{policy_name}' not found (should be auto-created)"
    assert auth_list.is_policy_listed(
        f"{policy_name}-callback"
    ), f"Callback AuthPolicy '{policy_name}-callback' not found (should be auto-created)"

    # Delete OIDCPolicy via UI
    oidc_list = navigator.navigate(OIDCPolicyListPage)
    oidc_list.delete(policy_name)

    # Verify OIDCPolicy is deleted from the list
    assert not oidc_list.is_policy_listed(policy_name), f"OIDCPolicy '{policy_name}' was not deleted"

    # Verify both child AuthPolicies were also deleted
    auth_list = navigator.navigate(AuthListPage)
    assert not auth_list.is_policy_listed(policy_name), f"Main AuthPolicy '{policy_name}' should be deleted with parent"
    assert not auth_list.is_policy_listed(
        f"{policy_name}-callback"
    ), f"Callback AuthPolicy '{policy_name}-callback' should be deleted with parent"

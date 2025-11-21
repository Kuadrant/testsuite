"""Verifies that a TLSPolicy can be created, listed, and deleted via the console plugin UI"""

import pytest

from testsuite.kuadrant.policy.tls import TLSPolicy
from testsuite.page_objects.policies.tls_policy import TLSNewPage, TLSListPage

pytestmark = [pytest.mark.ui]


@pytest.mark.parametrize("create_method", ["form", "yaml"])
def test_tls_policy_ui(request, navigator, cluster, blame, gateway, cluster_issuer, create_method):
    """Creates a TLSPolicy via the UI (form or YAML), verifies it appears, then deletes it via the UI"""

    # Prepare TLSPolicy data
    policy = TLSPolicy.create_instance(cluster, blame("tls"), parent=gateway, issuer=cluster_issuer)

    # Register finalizer to ensure cleanup via API if UI fails
    request.addfinalizer(policy.delete)

    # Navigate to the new TLS policy creation page
    new_page = navigator.navigate(TLSNewPage)

    # Use the appropriate policy creation method based on the parameter (form / yaml)
    if create_method == "form":
        new_page.create_form(policy)
    else:
        new_page.create_yaml(policy)

    # Verify TLSPolicy appears in the list
    list_page = navigator.navigate(TLSListPage)
    policy_name = policy.model.metadata.name
    assert list_page.get_policy(policy_name), f"TLSPolicy '{policy_name}' not found in list"

    # Delete TLSPolicy via UI
    list_page.delete(policy_name)

    # Verify TLSPolicy is deleted from the list
    assert not list_page.has_policy(policy_name), f"TLSPolicy '{policy_name}' was not deleted"

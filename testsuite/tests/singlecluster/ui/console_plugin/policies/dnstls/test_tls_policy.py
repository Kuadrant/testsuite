"""Verifies that a TLSPolicy can be created, listed, and deleted via the console plugin UI"""

import pytest

from testsuite.kuadrant.policy.tls import TLSPolicy
from testsuite.page_objects.policies.tls_policy import TLSNewPageYaml, TLSNewPageForm, TLSListPage

pytestmark = [pytest.mark.ui]


@pytest.fixture(autouse=True)
def remove_preexisting_tls(tls_policy):
    """Remove the TLS policy from conftest so we can create one via UI"""
    tls_policy.delete()
    yield


@pytest.mark.parametrize("tls_new_page", [TLSNewPageYaml, TLSNewPageForm])
def test_tls_policy_ui(request, navigator, cluster, blame, gateway, cluster_issuer, tls_new_page, client):
    """Creates a TLSPolicy via the UI (form or YAML), verifies it appears, then deletes it via the UI"""

    # Prepare TLSPolicy data
    policy = TLSPolicy.create_instance(cluster, blame("tls"), parent=gateway, issuer=cluster_issuer)

    # Register finalizer to ensure cleanup via API if UI fails
    request.addfinalizer(policy.delete)

    # Navigate to the new TLS policy creation page
    new_page = navigator.navigate(tls_new_page)
    assert new_page.page_displayed(), "TLSPolicy creation page did not load"
    new_page.create(policy)

    # Verify TLSPolicy appears in the list
    list_page = navigator.navigate(TLSListPage)
    assert list_page.page_displayed(), "TLSPolicy list page did not load"
    policy_name = policy.model.metadata.name
    assert list_page.is_policy_listed(policy_name), f"TLSPolicy '{policy_name}' not found in list"

    # Verify TLSPolicy created via UI enforces as expected
    response = client.get("/get")
    assert not response.has_cert_verify_error()
    assert response.status_code == 200

    # Delete TLSPolicy via UI
    list_page.delete(policy_name)

    # Verify TLSPolicy is deleted from the list
    assert not list_page.is_policy_listed(policy_name), f"TLSPolicy '{policy_name}' was not deleted"

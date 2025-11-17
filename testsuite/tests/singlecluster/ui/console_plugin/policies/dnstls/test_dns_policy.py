"""Verifies that a DNSPolicy can be created, listed, and deleted via the console plugin UI"""

import pytest

from testsuite.kuadrant.policy.dns import LoadBalancing, DNSPolicy
from testsuite.page_objects.policies.dns_policy import DNSNewPageYaml, DNSNewPageForm, DNSListPage

pytestmark = [pytest.mark.ui]


@pytest.fixture(scope="module")
def dns_policy():
    """Don't create DNSPolicy for this test"""
    return None


@pytest.mark.parametrize("dns_new_page", [DNSNewPageYaml, DNSNewPageForm])
def test_dns_policy_ui(
    request, navigator, cluster, blame, gateway, dns_provider_secret, dns_new_page, module_label, client
):
    """Creates a DNSPolicy via the UI (form or YAML), verifies it appears, then deletes it via the UI"""

    # Prepare DNSPolicy policy data
    load_balancing = LoadBalancing(defaultGeo=True, geo="CZ", weight=10)
    policy = DNSPolicy.create_instance(
        cluster, blame("dns"), gateway, dns_provider_secret, load_balancing=load_balancing, labels={"app": module_label}
    )

    # Register finalizer to ensure cleanup via API if UI fails
    request.addfinalizer(policy.delete)

    # Navigate to the DNS policy creation page
    new_page = navigator.navigate(dns_new_page)
    assert new_page.page_displayed(), "DNSPolicy creation page did not load"
    new_page.create(policy)

    # Verify DNSPolicy appears in the list
    list_page = navigator.navigate(DNSListPage)
    assert list_page.page_displayed(), "DNSPolicy list page did not load"
    policy_name = policy.model.metadata.name
    assert list_page.is_policy_listed(policy_name), f"DNSPolicy '{policy_name}' not found in list"

    # Verify DNSPolicy created via UI enforces as expected
    response = client.get("/get")
    assert not response.has_dns_error()
    assert response.status_code == 200

    # Delete DNSPolicy via UI
    list_page.delete(policy_name)

    # Verify DNSPolicy is deleted from the list
    assert not list_page.is_policy_listed(policy_name), f"DNSPolicy '{policy_name}' was not deleted"

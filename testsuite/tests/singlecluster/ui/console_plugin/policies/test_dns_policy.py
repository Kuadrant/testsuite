"""Verifies that a DNSPolicy can be created, listed, and deleted via the console plugin UI"""

import pytest

from testsuite.kuadrant.policy.dns import LoadBalancing, DNSPolicy
from testsuite.page_objects.policies.dns_policy import DNSNewPage, DNSListPage

pytestmark = [pytest.mark.ui]


@pytest.mark.parametrize("create_method", ["form", "yaml"])
def test_dns_policy_ui(request, navigator, cluster, blame, gateway, dns_provider_secret, create_method, module_label):
    """Creates a DNSPolicy via the UI (form or YAML), verifies it appears, then deletes it via the UI"""

    # Prepare DNSPolicy policy data
    load_balancing = LoadBalancing(defaultGeo=True, geo="EU", weight=10)
    policy = DNSPolicy.create_instance(
        cluster, blame("dns"), gateway, dns_provider_secret, load_balancing=load_balancing, labels={"app": module_label}
    )

    # Register finalizer to ensure cleanup via API if UI fails
    request.addfinalizer(policy.delete)

    # Navigate to the DNS policy creation page
    new_page = navigator.navigate(DNSNewPage)

    # Use the appropriate policy creation method based on the parameter (form / yaml)
    if create_method == "form":
        new_page.create_form(policy)
    else:
        new_page.create_yaml(policy)

    # Verify DNSPolicy appears in the list
    list_page = navigator.navigate(DNSListPage)
    policy_name = policy.model.metadata.name
    assert list_page.get_policy(policy_name), f"DNSPolicy '{policy_name}' not found in list"

    # Delete DNSPolicy via UI
    list_page.delete(policy_name)

    # Verify DNSPolicy is deleted from the list
    assert not list_page.has_policy(policy_name), f"DNSPolicy '{policy_name}' was not deleted"

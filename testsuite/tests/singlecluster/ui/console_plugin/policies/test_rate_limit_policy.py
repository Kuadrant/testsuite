"""Verifies that a RateLimitPolicy can be created, listed, and deleted via the console plugin UI"""

import pytest
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit
from testsuite.page_objects.policies.rate_limit_policy import RateLimitNewPage, RateLimitListPage

pytestmark = [pytest.mark.ui]


def test_rate_limit_policy_ui(request, navigator, cluster, blame, gateway):
    """Creates a RateLimitPolicy via the UI, verifies it appears, then deletes it via the UI"""

    # Prepare RateLimitPolicy data
    policy = RateLimitPolicy.create_instance(cluster, blame("limit"), gateway)
    policy.add_limit("basic", [Limit(3, "10s")])

    # Register finalizer to ensure cleanup via API if UI fails
    request.addfinalizer(policy.delete)

    # Navigate to RateLimitPolicy creation page and create policy via editor
    new_page = navigator.navigate(RateLimitNewPage)
    new_page.create(policy)

    # Verify RateLimitPolicy appears in the list
    list_page = navigator.navigate(RateLimitListPage)
    policy_name = policy.model.metadata.name
    assert list_page.get_policy(policy_name), f"RateLimitPolicy '{policy_name}' not found in list"

    # Delete RateLimitPolicy via UI
    list_page.delete(policy_name)

    # Verify RateLimitPolicy is deleted from the list
    assert not list_page.has_policy(policy_name), f"RateLimitPolicy '{policy_name}' was not deleted"

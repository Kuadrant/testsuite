"""Verifies that a RateLimitPolicy can be created, listed, and deleted via the console plugin UI"""

import pytest
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit
from testsuite.page_objects.policies.rate_limit_policy import RateLimitNewPageYaml, RateLimitListPage

pytestmark = [pytest.mark.ui]


def test_rate_limit_policy_ui(request, navigator, cluster, blame, gateway, client):
    """Creates a RateLimitPolicy via the UI, verifies it appears, then deletes it via the UI"""

    # Prepare RateLimitPolicy data
    policy = RateLimitPolicy.create_instance(cluster, blame("limit"), gateway)
    policy.add_limit("basic", [Limit(3, "10s")])

    # Register finalizer to ensure cleanup via API if UI fails
    request.addfinalizer(policy.delete)

    # Navigate to RateLimitPolicy creation page and create policy via editor
    new_page = navigator.navigate(RateLimitNewPageYaml)
    assert new_page.page_displayed(), "RateLimitPolicy creation page did not load"
    new_page.create(policy)

    # Verify RateLimitPolicy appears in the list
    list_page = navigator.navigate(RateLimitListPage)
    assert list_page.page_displayed(), "RateLimitPolicy list page did not load"
    policy_name = policy.model.metadata.name
    assert list_page.is_policy_listed(policy_name), f"RateLimitPolicy '{policy_name}' not found in list"

    # Verify RateLimitPolicy created via UI enforces as expected
    responses = client.get_many("/get", 3)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429

    # Delete RateLimitPolicy via UI
    list_page.delete(policy_name)

    # Verify RateLimitPolicy is deleted from the list
    assert not list_page.is_policy_listed(policy_name), f"RateLimitPolicy '{policy_name}' was not deleted"

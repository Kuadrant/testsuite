"""Verifies that a TokenRateLimitPolicy can be created, listed, and deleted via the console plugin UI"""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.kuadrant.policy.token_rate_limit import TokenRateLimitPolicy
from testsuite.page_objects.policies.token_rate_limit import TokenRateLimitNewPageYaml, TokenRateLimitListPage

pytestmark = [pytest.mark.ui]


@pytest.mark.min_ocp_version((4, 20))
@pytest.mark.flaky(reruns=0)
def test_token_rate_limit_policy_ui(request, navigator, cluster, blame, gateway):
    """Creates a TokenRateLimitPolicy via the UI, verifies it appears, then deletes it via the UI

    Note: this test does not verify enforcement. TokenRateLimitPolicy requires LLMsim setup to enforce.
    Enforcement is already tested in functional tests.
    """

    # Prepare TokenRateLimitPolicy data
    policy = TokenRateLimitPolicy.create_instance(cluster, blame("limit"), gateway)
    policy.add_limit("free", [Limit(10, "10s")])

    # Register finalizer to ensure cleanup via API if UI fails
    request.addfinalizer(policy.delete)

    # Navigate to TokenRateLimitPolicy creation page and create policy via editor
    new_page = navigator.navigate(TokenRateLimitNewPageYaml)
    assert new_page.page_displayed(), "TokenRateLimitPolicy creation page did not load"
    new_page.create(policy)

    # Verify TokenRateLimitPolicy appears in the list
    list_page = navigator.navigate(TokenRateLimitListPage)
    assert list_page.page_displayed(), "TokenRateLimitPolicy list page did not load"
    policy_name = policy.model.metadata.name
    assert list_page.is_policy_listed(policy_name), f"TokenRateLimitPolicy '{policy_name}' not found in list"

    # Delete TokenRateLimitPolicy via UI
    list_page.delete(policy_name)

    # Verify TokenRateLimitPolicy is deleted from the list
    assert not list_page.is_policy_listed(policy_name), f"TokenRateLimitPolicy '{policy_name}' was not deleted"

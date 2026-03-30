"""Verifies that a PlanPolicy can be created, listed, and deleted via the console plugin UI"""

import pytest

from testsuite.kuadrant.extensions.plan_policy import PlanPolicy, Plan
from testsuite.page_objects.policies.plan_policy import PlanPolicyNewPageYaml, PlanPolicyListPage
from testsuite.page_objects.policies.rate_limit_policy import RateLimitListPage

pytestmark = [pytest.mark.ui]


@pytest.mark.min_ocp_version((4, 20))
def test_plan_policy_ui(request, navigator, cluster, blame, gateway):
    """Creates a PlanPolicy via the UI, verifies it appears, then deletes it via the UI

    Also verifies child RateLimitPolicy is auto-created and cascade deleted.

    Note: this test does not verify enforcement. PlanPolicy requires AuthPolicy + OIDC setup to enforce.
    Enforcement is already tested in functional tests.
    """

    # Prepare PlanPolicy data
    policy = PlanPolicy.create_instance(cluster, blame("plan"), gateway)
    policy.add_plan(
        Plan(
            tier="basic",
            predicate='request.method == "GET"',
            limits={"daily": 1000},
        )
    )

    # Register finalizer to ensure cleanup via API if UI fails
    request.addfinalizer(policy.delete)

    # Navigate to PlanPolicy creation page and create policy via editor
    new_page = navigator.navigate(PlanPolicyNewPageYaml)
    assert new_page.page_displayed(), "PlanPolicy creation page did not load"
    new_page.create(policy)

    # Verify PlanPolicy appears in the list
    list_page = navigator.navigate(PlanPolicyListPage)
    assert list_page.page_displayed(), "PlanPolicy list page did not load"
    policy_name = policy.model.metadata.name
    assert list_page.is_policy_listed(policy_name), f"PlanPolicy '{policy_name}' not found in list"

    # Verify child RateLimitPolicy was automatically created
    rlp_list_page = navigator.navigate(RateLimitListPage)
    assert rlp_list_page.page_displayed(), "RateLimitPolicy list page did not load"
    # Child RLP has same name as parent PlanPolicy
    assert rlp_list_page.is_policy_listed(
        policy_name
    ), f"Child RateLimitPolicy '{policy_name}' not found (should be auto-created)"

    # Delete PlanPolicy via UI
    list_page = navigator.navigate(PlanPolicyListPage)
    list_page.delete(policy_name)

    # Verify PlanPolicy is deleted from the list
    assert not list_page.is_policy_listed(policy_name), f"PlanPolicy '{policy_name}' was not deleted"

    # Verify child RateLimitPolicy was also deleted
    rlp_list_page = navigator.navigate(RateLimitListPage)
    assert not rlp_list_page.is_policy_listed(
        policy_name
    ), f"Child RateLimitPolicy '{policy_name}' should be deleted with parent"

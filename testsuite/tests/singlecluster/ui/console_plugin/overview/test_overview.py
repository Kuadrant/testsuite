"""UI tests for Overview page sections"""

import pytest
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit
from testsuite.page_objects.overview.gateway import GatewayNewPageYaml
from testsuite.page_objects.overview.httproute import HTTPRouteNewPageYaml
from testsuite.page_objects.overview.overview_page import OverviewPage
from testsuite.page_objects.overview.policy import PolicyDetailsPage
from testsuite.page_objects.policies.rate_limit_policy import RateLimitNewPageYaml

pytestmark = [pytest.mark.ui]


def test_getting_started_section(navigator):
    """Verify Getting started resources section displays all expected cards and links"""
    # Navigate to overview page
    overview_page = navigator.navigate(OverviewPage)
    assert overview_page.page_displayed(), "Overview page did not load"

    # Verify the Getting started resources section is present
    assert overview_page.has_getting_started_section(), "Getting started resources section not found"

    # Check resource cards
    assert overview_page.has_learning_resources(), "Learning Resources card not found"
    assert overview_page.has_feature_highlights(), "Feature Highlights card not found"
    assert overview_page.has_operations_tools(), "Operations & Tools / Enhance Your Work card not found"

    # Check links in each card
    assert overview_page.has_view_documentation_link(), "View Documentation link not found"
    assert overview_page.has_view_config_and_deploy_link(), "Configuring and deploying Gateway policies link not found"
    assert overview_page.has_release_notes_link(), "Release Notes link not found"
    assert overview_page.has_observability_link(), "Observability link not found"
    assert overview_page.has_cert_manager_link(), "cert-manager Operator link not found"


def test_gateways_section(navigator):
    """Verify Gateways status section displays all metrics in empty state"""
    overview_page = navigator.navigate(OverviewPage)
    assert overview_page.page_displayed(), "Overview page did not load"

    # Check Gateways section and metrics
    assert overview_page.has_gateways_section(), "Gateways section not found"
    assert overview_page.has_total_gateways_metric(), "Total Gateways metric not found"
    assert overview_page.has_healthy_gateways_metric(), "Healthy Gateways metric not found"
    assert overview_page.has_unhealthy_gateways_metric(), "Unhealthy Gateways metric not found"


def test_gateways_analysis_section(request, navigator, cluster, blame):
    """Create Gateway via overview UI, verify metrics transition from unhealthy to healthy, then delete"""
    gateway_name = blame("gw")

    # Register finalizer for cleanup
    request.addfinalizer(lambda: cluster.do_action("delete", "gateway", gateway_name, auto_raise=False))

    overview_page = navigator.navigate(OverviewPage)
    assert overview_page.page_displayed(), "Overview page did not load"

    # Verify the Gateways - Traffic Analysis section is present
    assert overview_page.has_gateways_traffic_section(), "Gateways - Traffic Analysis section not found"

    # Navigate to gateway creation page and create gateway
    gateway_page = navigator.navigate(GatewayNewPageYaml)
    assert gateway_page.page_displayed(), "Gateway creation page did not load"
    gateway_page.create(name=gateway_name)

    # Navigate back to overview page to verify gateway appears in list
    overview_page = navigator.navigate(OverviewPage)
    assert overview_page.page_displayed(), "Overview page did not load"
    assert overview_page.has_gateway_in_traffic_analysis(gateway_name), "Gateway not visible in traffic analysis"

    # Verify gateway metrics are updated
    assert overview_page.get_total_gateways_count() >= 1, "Total Gateways count should be at least 1"
    assert (
        overview_page.get_unhealthy_gateways_count() >= 1
    ), "Unhealthy Gateways count should be at least 1 before it becomes healthy"

    # Wait for gateway to become healthy
    assert overview_page.wait_for_healthy_gateways(1), "Gateway did not become healthy within timeout"

    # Delete Gateway via UI
    overview_page.click_gateway(gateway_name)
    gateway_page.delete()


def test_policies_section(request, navigator, cluster, blame, gateway, client):
    """
    Create RateLimitPolicy via overview UI, verify it appears and enforces correctly, then delete

    Uses RateLimitPolicy as sample - other policy types are tested in the policy tests
    """
    # Prepare RateLimitPolicy data
    policy = RateLimitPolicy.create_instance(cluster, blame("limit"), gateway)
    policy.add_limit("basic", [Limit(3, "10s")])

    # Register finalizer for cleanup
    request.addfinalizer(policy.delete)

    overview_page = navigator.navigate(OverviewPage)
    assert overview_page.page_displayed(), "Overview page did not load"

    # Verify the Policies section is present
    assert overview_page.has_policies_section(), "Policies section not found"

    # Click Create Policy button, then click RateLimitPolicy to navigate to creation page
    overview_page.new_policy()
    overview_page.page.get_by_role("menuitem", name="RateLimitPolicy", exact=True).click()

    # Create policy via YAML editor
    rate_limit_new_page = RateLimitNewPageYaml(overview_page.page)
    assert rate_limit_new_page.page_displayed(), "RateLimitPolicy creation page did not load"
    rate_limit_new_page.create(policy)

    # Navigate back to overview page to verify policy appears
    overview_page = navigator.navigate(OverviewPage)
    assert overview_page.page_displayed(), "Overview page did not load"
    policy_name = policy.model.metadata.name
    assert overview_page.has_policy_in_section(policy_name), f"RateLimitPolicy '{policy_name}' not visible in overview"

    # Verify RateLimitPolicy created via UI enforces as expected
    responses = client.get_many("/get", 3)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429

    # Click policy name to go to details page and delete
    overview_page.click_policy(policy_name)

    # Delete Policy via UI
    policy_details_page = PolicyDetailsPage(overview_page.page, "RateLimitPolicy")
    policy_details_page.delete()


def test_httproute_section(request, navigator, cluster, blame):
    """Create HTTPRoute via overview UI, verify it appears in HTTPRoutes section, then delete"""
    httproute_name = blame("httproute")

    # Register finalizer for cleanup
    request.addfinalizer(lambda: cluster.do_action("delete", "httproute", httproute_name, auto_raise=False))

    overview_page = navigator.navigate(OverviewPage)
    assert overview_page.page_displayed(), "Overview page did not load"

    # Verify the HTTPRoutes section is present
    assert overview_page.has_httproute_section(), "HTTPRoute section not found"

    # Navigate to HTTPRoute creation page and create HTTPRoute
    httproute_page = navigator.navigate(HTTPRouteNewPageYaml)
    assert httproute_page.page_displayed(), "HTTPRoute creation page did not load"
    httproute_page.create(name=httproute_name)

    # Navigate back to overview page to verify HTTPRoute appears
    overview_page = navigator.navigate(OverviewPage)
    assert overview_page.page_displayed(), "Overview page did not load"
    assert overview_page.has_httproute_in_section(httproute_name), "HTTPRoute not visible in section"

    # Delete HTTPRoutes via UI
    overview_page.click_httproute(httproute_name)
    httproute_page.delete()

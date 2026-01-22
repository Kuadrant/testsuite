"""UI tests for console plugin Overview page"""

import pytest
from testsuite.gateway import GatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.page_objects.overview.overview_page import OverviewPage

pytestmark = [pytest.mark.ui]


def test_overview_page_sections_and_links(navigator):
    """Verify all section panels are visible and Getting started resources has clickable links"""
    # Navigate to overview page
    overview_page = navigator.navigate(OverviewPage)
    assert overview_page.page_displayed(), "Overview page did not load"

    # Verify all expected section panels exist
    getting_started = overview_page.page.get_by_text("Getting started resources")
    assert getting_started.is_visible()
    assert overview_page.page.get_by_role("heading", name="Gateways", exact=True).is_visible()
    assert overview_page.page.get_by_role("heading", name="Gateways - Traffic Analysis", exact=True).is_visible()
    assert overview_page.page.get_by_role("heading", name="Policies", exact=True).is_visible()
    assert overview_page.page.get_by_role("heading", name="HTTPRoutes", exact=True).is_visible()

    # Verify Getting started resources panel has clickable links
    getting_started_section = getting_started.locator("xpath=ancestor::section").first
    links = getting_started_section.get_by_role("link").all()
    clickable_links = [link for link in links if link.is_visible() and link.is_enabled()]
    assert len(clickable_links) > 0, "No clickable links found in Getting started resources panel"


def test_creation_buttons(navigator):
    """Verify creation buttons are clickable and policy dropdown shows available policy types"""
    # Navigate to overview page
    overview_page = navigator.navigate(OverviewPage)
    assert overview_page.page_displayed(), "Overview page did not load"

    # Verify Create Gateway button is visible and clickable
    create_gateway = overview_page.page.get_by_text("Create Gateway")
    assert create_gateway.is_visible() and create_gateway.is_enabled()

    # Verify Create HTTPRoute button is visible and clickable
    create_httproute = overview_page.page.get_by_text("Create HTTPRoute")
    assert create_httproute.is_visible() and create_httproute.is_enabled()

    # Verify Create Policy button is visible and clickable, then open dropdown
    create_policy = overview_page.page.get_by_text("Create Policy")
    assert create_policy.is_visible() and create_policy.is_enabled()
    create_policy.click()

    # Verify core policies are visible in the dropdown
    core_policies = ["AuthPolicy", "RateLimitPolicy", "DNSPolicy", "TLSPolicy"]
    for policy_type in core_policies:
        menu_item = overview_page.page.get_by_role("menuitem", name=policy_type, exact=True)
        assert menu_item.is_visible(), f"{policy_type} should be visible"
        assert menu_item.is_enabled(), f"{policy_type} should be enabled"


@pytest.mark.min_ocp_version((4, 20))
def test_additional_policy_types_in_dropdown(navigator):
    """Verify additional policy types appear in Create Policy dropdown (OCP 4.20+)"""
    overview_page = navigator.navigate(OverviewPage)
    assert overview_page.page_displayed(), "Overview page did not load"

    # Open Create Policy dropdown
    create_policy = overview_page.page.get_by_text("Create Policy")
    assert create_policy.is_visible() and create_policy.is_enabled()
    create_policy.click()

    # Verify additional policies available in OCP 4.20+
    additional_policies = ["OIDCPolicy", "PlanPolicy", "TokenRateLimitPolicy"]
    for policy_type in additional_policies:
        menu_item = overview_page.page.get_by_role("menuitem", name=policy_type, exact=True)
        assert menu_item.is_visible(), f"{policy_type} should be visible in OCP 4.20+"
        assert menu_item.is_enabled(), f"{policy_type} should be enabled"


def test_resources_appear_in_sections(request, navigator, cluster, blame, module_label, wildcard_domain, backend):
    """Verify gateway, HTTPRoute, and policy resources appear in their respective section panels"""
    # Create resources programmatically
    gateway_name = blame("gw")
    gateway = KuadrantGateway.create_instance(cluster, gateway_name, {"app": module_label})
    gateway.add_listener(GatewayListener(hostname=wildcard_domain))
    request.addfinalizer(gateway.delete)
    gateway.commit()

    route_name = blame("route")
    route = HTTPRoute.create_instance(cluster, route_name, gateway)
    route.add_backend(backend)
    request.addfinalizer(route.delete)
    route.commit()

    policy_name = blame("policy")
    policy = AuthPolicy.create_instance(cluster, policy_name, gateway)
    policy.authorization.add_opa_policy("denyAll", "allow = false")
    request.addfinalizer(policy.delete)
    policy.commit()

    # Navigate to overview page
    overview_page = navigator.navigate(OverviewPage)
    assert overview_page.page_displayed(), "Overview page did not load"

    # Verify gateway appears in Gateways - Traffic Analysis section panel
    assert overview_page.has_gateway_in_traffic_analysis(
        gateway_name
    ), f"Gateway '{gateway_name}' not visible in traffic analysis section panel"

    # Verify HTTPRoute appears in HTTPRoutes section panel
    assert overview_page.has_httproute_in_section(
        route_name
    ), f"HTTPRoute '{route_name}' not visible in HTTPRoutes section panel"

    # Verify policy appears in Policies section panel
    assert overview_page.has_policy_in_section(
        policy_name
    ), f"Policy '{policy_name}' not visible in Policies section panel"


def test_gateway_section_status(request, navigator, cluster, blame, module_label, wildcard_domain):
    """Verify gateway status metrics display correctly"""
    # Create gateway programmatically
    gateway_name = blame("gw")
    gateway = KuadrantGateway.create_instance(cluster, gateway_name, {"app": module_label})
    gateway.add_listener(GatewayListener(hostname=wildcard_domain))
    request.addfinalizer(gateway.delete)
    gateway.commit()

    # Navigate to overview page
    overview_page = navigator.navigate(OverviewPage)
    assert overview_page.page_displayed(), "Overview page did not load"

    # Wait for the gateway to appear in the UI to ensure metrics have updated
    assert overview_page.has_gateway_in_traffic_analysis(
        gateway_name
    ), f"Gateway '{gateway_name}' not visible in traffic analysis section"

    # Check current gateway state - it should be either unhealthy (provisioning) or healthy (fast infra)
    unhealthy_count = overview_page.get_metric_count("Unhealthy Gateways")
    healthy_count = overview_page.get_metric_count("Healthy Gateways")
    total_count = overview_page.get_metric_count("Total Gateways")

    # Verify metrics display the gateway in initial state
    assert total_count >= 1, f"Should have at least 1 gateway, found {total_count}"
    assert (
        unhealthy_count >= 1 or healthy_count >= 1
    ), f"Gateway should appear in either unhealthy ({unhealthy_count}) or healthy ({healthy_count}) count"

    # Wait for gateway to transition to ready state
    gateway.wait_for_ready()

    # Refresh UI
    overview_page.page.reload()
    assert overview_page.page_displayed(), "Overview page did not load after reload"

    # Verify gateway is reflected as healthy after becoming ready
    final_healthy_count = overview_page.get_metric_count("Healthy Gateways")
    assert final_healthy_count >= 1, f"Should have at least 1 healthy gateway, found {final_healthy_count}"

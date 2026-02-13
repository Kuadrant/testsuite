"""UI tests for console plugin Overview page"""

import pytest
from testsuite.gateway import GatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.page_objects.overview.overview_page import OverviewPage

pytestmark = [pytest.mark.ui]


def test_overview_page_panels_and_links(navigator):
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
    assert overview_page.page.get_by_role("menuitem", name="AuthPolicy", exact=True).is_visible()
    assert overview_page.page.get_by_role("menuitem", name="RateLimitPolicy", exact=True).is_visible()
    assert overview_page.page.get_by_role("menuitem", name="DNSPolicy", exact=True).is_visible()
    assert overview_page.page.get_by_role("menuitem", name="TLSPolicy", exact=True).is_visible()

    # Check for additional policies (available in OCP 4.20+)
    additional_policies = ["OIDCPolicy", "PlanPolicy", "TokenRateLimitPolicy"]
    for policy_type in additional_policies:
        menu_item = overview_page.page.get_by_role("menuitem", name=policy_type, exact=True)
        if menu_item.is_visible():
            # If the policy option exists, verify it's enabled/clickable
            assert menu_item.is_enabled(), f"{policy_type} is visible but not enabled"


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
    """Verify gateway status metrics update correctly"""
    # Navigate to overview page and capture initial counts
    overview_page = navigator.navigate(OverviewPage)
    assert overview_page.page_displayed(), "Overview page did not load"

    initial_total = overview_page.get_metric_count("Total Gateways")
    initial_healthy = overview_page.get_metric_count("Healthy Gateways")
    initial_unhealthy = overview_page.get_metric_count("Unhealthy Gateways")

    # Create gateway programmatically
    gateway_name = blame("gw")
    gateway = KuadrantGateway.create_instance(cluster, gateway_name, {"app": module_label})
    gateway.add_listener(GatewayListener(hostname=wildcard_domain))
    request.addfinalizer(gateway.delete)
    gateway.commit()

    # Refresh page to see updated metrics
    overview_page = navigator.navigate(OverviewPage)
    assert overview_page.page_displayed(), "Overview page did not load"

    # Verify total gateway count increased
    new_total = overview_page.get_metric_count("Total Gateways")
    assert new_total > initial_total, f"Total Gateways count did not increase (was {initial_total}, now {new_total})"

    # Verify unhealthy count increased (gateway starts as unhealthy while provisioning)
    new_unhealthy = overview_page.get_metric_count("Unhealthy Gateways")
    assert (
        new_unhealthy > initial_unhealthy
    ), f"Unhealthy count did not increase (was {initial_unhealthy}, now {new_unhealthy})"

    # Wait for gateway to become healthy and verify healthy count increased
    overview_page.wait_for_healthy_gateways(initial_healthy + 1)
    new_healthy = overview_page.get_metric_count("Healthy Gateways")
    assert new_healthy > initial_healthy, f"Healthy count did not increase (was {initial_healthy}, now {new_healthy})"

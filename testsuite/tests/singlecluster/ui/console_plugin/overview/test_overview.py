"""UI tests for console plugin Overview page"""

import pytest
from testsuite.gateway import GatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.grpc_route import GRPCRoute
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.page_objects.overview.overview_page import OverviewPage

pytestmark = [pytest.mark.ui]


def test_overview_page_sections_and_links(navigator, openshift_version):
    """Verify all section panels are visible and getting started banner has documentation link"""
    # Navigate to overview page
    overview_page = navigator.navigate(OverviewPage)
    assert overview_page.page_displayed(), "Overview page did not load"

    # Verify getting started banner has a clickable documentation link
    assert overview_page.page.get_by_text("Getting started with").is_visible()
    view_doc_link = overview_page.page.get_by_role("link", name="View Documentation")
    assert view_doc_link.is_visible() and view_doc_link.is_enabled()

    # Verify all expected section panels exist
    assert overview_page.page.get_by_role("heading", name="Gateways", exact=True).is_visible()
    assert overview_page.page.get_by_role("heading", name="Gateways - Traffic Analysis", exact=True).is_visible()
    assert overview_page.page.get_by_role("heading", name="Policies", exact=True).is_visible()
    assert overview_page.page.get_by_role("heading", name="HTTPRoutes", exact=True).is_visible()
    # GRPCRoutes section only on OCP 4.20+
    if openshift_version >= (4, 20):
        assert overview_page.page.get_by_role("heading", name="GRPCRoutes", exact=True).is_visible()


def test_creation_buttons(navigator, openshift_version):
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

    # Verify Create GRPCRoute button is visible and clickable (OCP 4.20+)
    if openshift_version >= (4, 20):
        create_grpcroute = overview_page.page.get_by_text("Create GRPCRoute")
        assert create_grpcroute.is_visible() and create_grpcroute.is_enabled()

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


def test_resources_appear_in_sections(
    request, navigator, cluster, blame, module_label, wildcard_domain, backend, openshift_version
):
    """Verify gateway, HTTPRoute, GRPCRoute (OCP 4.20+), and policy resources appear in section panels"""
    # Create gateway
    gw_name = blame("gw")
    gw = KuadrantGateway.create_instance(cluster, gw_name, {"app": module_label})
    gw.add_listener(GatewayListener(hostname=wildcard_domain))
    request.addfinalizer(gw.delete)
    gw.commit()

    # Create HTTPRoute
    http_route = HTTPRoute.create_instance(cluster, blame("route"), gw)
    http_route.add_backend(backend)
    request.addfinalizer(http_route.delete)
    http_route.commit()
    http_route.wait_for_ready()

    # Create GRPCRoute only on OCP 4.20+
    grpc_route = None
    if openshift_version >= (4, 20):
        grpc_route = GRPCRoute.create_instance(cluster, blame("grpc"), gw)
        request.addfinalizer(grpc_route.delete)
        grpc_route.commit()
        grpc_route.wait_for_ready()

    # Create AuthPolicy
    auth_name = blame("policy")
    auth = AuthPolicy.create_instance(cluster, auth_name, gw)
    auth.authorization.add_opa_policy("denyAll", "allow = false")
    request.addfinalizer(auth.delete)
    auth.commit()

    # Navigate to overview page
    overview_page = navigator.navigate(OverviewPage)
    assert overview_page.page_displayed(), "Overview page did not load"

    # Verify gateway appears in Gateways - Traffic Analysis section panel
    assert overview_page.has_gateway_in_traffic_analysis(
        gw_name
    ), f"Gateway '{gw_name}' not visible in traffic analysis section panel"

    # Verify HTTPRoute appears in HTTPRoutes section panel
    assert overview_page.has_httproute_in_section(
        http_route.model.metadata.name
    ), f"HTTPRoute '{http_route.model.metadata.name}' not visible in HTTPRoutes section panel"

    # Verify GRPCRoute appears in GRPCRoutes section panel (OCP 4.20+)
    if grpc_route:
        assert overview_page.has_grpcroute_in_section(
            grpc_route.model.metadata.name
        ), f"GRPCRoute '{grpc_route.model.metadata.name}' not visible in GRPCRoutes section panel"

    # Verify policy appears in Policies section panel
    assert overview_page.has_policy_in_section(auth_name), f"Policy '{auth_name}' not visible in Policies section panel"


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

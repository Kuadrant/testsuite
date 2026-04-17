"""UI tests for console plugin Policy Topology page"""

import pytest
from testsuite.page_objects.topology.topology_page import TopologyPage
from testsuite.tests.singlecluster.ui.console_plugin.constants import UI_NAVIGATION_TIMEOUT

pytestmark = [pytest.mark.ui]


def test_topology_page_loads(navigator):
    """Navigate to topology page and verify key sections display"""
    # Navigate to topology page
    topology_page = navigator.navigate(TopologyPage)
    assert topology_page.page_displayed(), "Topology page did not load"

    # Verify filter controls and topology view section are visible
    assert topology_page.get_resource_dropdown().is_visible(), "Resource dropdown not visible"
    topology_view_heading = topology_page.page.get_by_text("Topology View")
    assert topology_view_heading.is_visible(), "Topology View heading not visible"

    # Verify the topology graph SVG renders
    svg_graph = topology_page.page.locator("svg.pf-topology-visualization-surface__svg")
    svg_graph.wait_for(state="visible", timeout=UI_NAVIGATION_TIMEOUT)
    assert svg_graph.is_visible(), "Topology graph SVG not visible"


def test_topology_resources_appear(navigator, gateway, route, authorization, rate_limit, dns_policy, tls_policy):
    """Verify topology displays all resources and their connections"""
    # Navigate to topology page
    topology_page = navigator.navigate(TopologyPage)
    assert topology_page.page_displayed(), "Topology page did not load"

    # Verify all resources and policies are visible in topology
    assert topology_page.has_resource_node(gateway.model.metadata.name), "Gateway not found in topology"
    assert topology_page.has_resource_node(route.model.metadata.name), "HTTPRoute not found in topology"
    assert topology_page.has_resource_node(authorization.model.metadata.name), "AuthPolicy not found in topology"
    assert topology_page.has_resource_node(rate_limit.model.metadata.name), "RateLimitPolicy not found in topology"
    assert topology_page.has_resource_node(dns_policy.model.metadata.name), "DNSPolicy not found in topology"
    assert topology_page.has_resource_node(tls_policy.model.metadata.name), "TLSPolicy not found in topology"

    # Verify topology shows connections between resources
    assert topology_page.has_connections(), "No connections found in topology"


def test_topology_filters_work(navigator, gateway, route, cluster):
    """Verify namespace and resource filters control which resources are shown"""
    # Navigate to topology page
    topology_page = navigator.navigate(TopologyPage)
    assert topology_page.page_displayed(), "Topology page did not load"

    # Test namespace filter
    topology_page.select_namespace(cluster.project)

    # Verify namespace filter is active
    assert topology_page.is_filter_active(
        cluster.project
    ), f"Namespace filter '{cluster.project}' not active after selection"

    # Clear all filters
    topology_page.reset_all_filters()
    assert topology_page.get_active_filter_count() == 0, "Active filters found after reset"

    # Apply filters and verify resources appear
    topology_page.apply_resource_filter("Gateway")
    topology_page.apply_resource_filter("HTTPRoute")
    assert topology_page.is_filter_active("Gateway"), "Gateway filter not active"
    assert topology_page.is_filter_active("HTTPRoute"), "HTTPRoute filter not active"
    assert topology_page.has_resource_node(gateway.model.metadata.name), "Gateway not visible with filter active"
    assert topology_page.has_resource_node(route.model.metadata.name), "HTTPRoute not visible with filter active"

    # Remove Gateway filter and verify it disappears
    topology_page.remove_filter("Gateway")
    assert not topology_page.is_filter_active("Gateway"), "Gateway filter still active after removal"
    assert topology_page.is_filter_active("HTTPRoute"), "HTTPRoute filter was removed when removing Gateway filter"
    assert topology_page.resource_node_hidden(gateway.model.metadata.name), "Gateway still visible after filter removal"
    assert topology_page.has_resource_node(
        route.model.metadata.name
    ), "HTTPRoute not visible after removing Gateway filter"

    # Reset all filters
    topology_page.reset_all_filters()
    assert topology_page.get_active_filter_count() == 0, "Active filters found after reset"

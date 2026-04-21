"""Page object for the console plugin Policy Topology page"""

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, expect
from testsuite.page_objects.navigator import Navigable
from testsuite.tests.singlecluster.ui.console_plugin.constants import (
    UI_PAGE_LOAD_TIMEOUT,
    UI_ELEMENT_TIMEOUT,
    UI_SESSION_INIT_TIMEOUT,
)


class TopologyPage(Navigable):
    """Page object for Policy Topology page"""

    def __init__(self, page: Page):
        super().__init__(page)
        self.page_heading = page.locator("h1").filter(has_text="Policy Topology")

    def is_displayed(self):
        """Returns the page heading locator"""
        return self.page_heading

    def page_displayed(self):
        """Check if the topology page is displayed"""
        self.page_heading.wait_for(state="visible", timeout=UI_PAGE_LOAD_TIMEOUT)
        return True

    def get_resource_dropdown(self):
        """Get the Resource filter dropdown button (PF5 and PF6 compatible)"""
        return self.page.locator(
            "//button[(contains(@class, 'pf-v6-c-menu-toggle') or contains(@class, 'pf-v5-c-menu-toggle')) "
            "and contains(., 'Resource')]"
        ).first

    def get_namespace_dropdown(self):
        """Get the Namespace filter dropdown button"""
        return self.page.locator("//button[contains(@class, 'pf-v6-c-menu-toggle') and contains(., 'Namespace')]").first

    def select_namespace(self, namespace: str):
        """Select a specific namespace from the namespace dropdown"""
        dropdown = self.get_namespace_dropdown()
        dropdown.click()

        # Find and click the namespace menu item
        namespace_option = self.page.locator(
            f"//li[contains(@class, 'pf-v6-c-menu__list-item')]//span[text()='{namespace}']"
        ).first
        namespace_option.wait_for(state="visible", timeout=UI_ELEMENT_TIMEOUT)
        namespace_option.click()

    def click_reset_filters_link(self):
        """Click the 'Reset Filters' link to clear all filters"""
        reset_link = self.page.get_by_text("Reset Filters")
        reset_link.click()

    def is_filter_active(self, filter_name: str):
        """Check if a resource filter is currently active by looking for its label chip"""
        label_chip = self.page.locator(
            f"//ul[contains(@class, 'pf-v6-c-label-group__list')]"
            f"//span[contains(@class, 'pf-v6-c-label__text') and text()='{filter_name}']"
        )
        try:
            label_chip.wait_for(state="visible", timeout=UI_SESSION_INIT_TIMEOUT)
            return True
        except PlaywrightTimeoutError:
            return False

    def apply_resource_filter(self, resource_type: str):
        """Apply a resource type filter (e.g., 'Gateway', 'Authorino', 'DNSPolicy')"""
        dropdown = self.get_resource_dropdown()
        dropdown.click()

        # Find the checkbox by the label text
        # Use exact=True to avoid matching "Gateway" with "GatewayClass"
        checkbox = self.page.get_by_role("checkbox", name=resource_type, exact=True)

        # Wait for the checkbox to be visible before clicking
        checkbox.wait_for(state="visible", timeout=UI_ELEMENT_TIMEOUT)

        # Only click if not already checked
        if not checkbox.is_checked():
            checkbox.click()

        # Close the dropdown
        dropdown.click()

    def remove_filter(self, filter_name: str):
        """Remove an active filter by unchecking it in the dropdown"""
        dropdown = self.get_resource_dropdown()
        dropdown.click()

        # Find the checkbox by its name
        # Use exact=True to avoid matching "Gateway" with "GatewayClass"
        checkbox = self.page.get_by_role("checkbox", name=filter_name, exact=True)

        # Wait for the checkbox to be visible
        checkbox.wait_for(state="visible", timeout=UI_ELEMENT_TIMEOUT)

        # Only click if currently checked
        if checkbox.is_checked():
            checkbox.click()

        # Close the dropdown
        dropdown.click()

    def reset_all_filters(self):
        """Clear all filters by clicking the Reset Filters link and wait for them to clear"""
        self.click_reset_filters_link()
        # Wait for all active filter label chips to be removed from the DOM
        active_filter_labels = self.page.locator(
            "//ul[contains(@class, 'pf-v6-c-label-group__list')]" + "//span[contains(@class, 'pf-v6-c-label__text')]"
        )
        expect(active_filter_labels).to_have_count(0, timeout=UI_ELEMENT_TIMEOUT)

    def has_resource_node(self, resource_name: str):
        """Check if a resource node appears in the topology graph"""
        node = self.page.locator(
            f"//*[contains(@data-test-id, '{resource_name}') or contains(text(), '{resource_name}')]"
        ).first
        try:
            node.wait_for(state="visible", timeout=UI_ELEMENT_TIMEOUT)
            return True
        except PlaywrightTimeoutError:
            return False

    def resource_node_hidden(self, resource_name: str):
        """Wait for a resource node to be hidden from the topology graph"""
        node = self.page.locator(
            f"//*[contains(@data-test-id, '{resource_name}') or contains(text(), '{resource_name}')]"
        ).first
        try:
            node.wait_for(state="hidden", timeout=UI_ELEMENT_TIMEOUT)
            return True
        except PlaywrightTimeoutError:
            return False

    def has_connections(self):
        """Check if the topology graph shows any connections/edges between resources"""
        # Topology graphs use SVG lines/paths to show connections between nodes
        edge = self.page.locator(
            "//*[name()='line' or name()='path'][contains(@class, 'edge') or contains(@class, 'connection')]"
        ).first
        try:
            edge.wait_for(state="visible", timeout=UI_ELEMENT_TIMEOUT)
            return True
        except PlaywrightTimeoutError:
            return False

    def get_active_filter_count(self):
        """Get the count of currently active filters from the dropdown badge"""
        # When there are no filters, the badge doesn't exist
        badge = self.page.locator(
            "//button[contains(@class, 'pf-v6-c-menu-toggle') and contains(., 'Resource')]"
            "//span[contains(@class, 'pf-v6-c-badge')]"
        )
        if not badge.is_visible():
            return 0
        badge_text = badge.text_content()
        return int(badge_text.strip()) if badge_text else 0

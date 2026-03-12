"""Page object for the console plugin Overview page"""

import backoff
from playwright.sync_api import Page
from testsuite.page_objects.navigator import Navigable


class OverviewPage(Navigable):
    """Page object for Overview page"""

    def __init__(self, page: Page):
        super().__init__(page)
        self.page_heading = page.locator("h1").filter(has_text="Overview")

    def is_displayed(self):
        """Returns the page heading locator"""
        return self.page_heading

    def page_displayed(self):
        """Check if the overview page is displayed"""
        self.page_heading.wait_for(state="visible", timeout=60000)
        return self.page_heading.is_visible()

    def get_metric_count(self, metric_name: str):
        """Get the count from a gateway metric card"""
        metric_card = self.page.locator(f"//div[contains(., '{metric_name}')]").first
        count_element = metric_card.locator("strong").first
        return int(count_element.inner_text().strip())

    @backoff.on_predicate(backoff.constant, interval=2, max_tries=30, jitter=None)
    def wait_for_healthy_gateways(self, expected_count: int):
        """Wait for the healthy gateways count to reach the expected value"""
        return self.get_metric_count("Healthy Gateways") >= expected_count

    def has_gateway_in_traffic_analysis(self, gateway_name: str):
        """Check if gateway appears in traffic analysis section"""
        return self.page.wait_for_selector(f"//tr//a[@data-test-id='{gateway_name}']")

    def has_httproute_in_section(self, route_name: str):
        """Check if HTTPRoute appears in HTTPRoutes section"""
        return self.page.wait_for_selector(f"//tr//a[@data-test-id='{route_name}']")

    def has_policy_in_section(self, policy_name: str):
        """Check if policy appears in Policies section"""
        return self.page.wait_for_selector(f"//tr//a[@data-test-id='{policy_name}']")

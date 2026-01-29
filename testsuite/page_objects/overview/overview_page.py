"""Overview landing page for the console plugin"""

import re

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from testsuite.page_objects.navigator import Navigable, step
from testsuite.page_objects.overview.gateway import GatewayNewPageYaml
from testsuite.page_objects.overview.httproute import HTTPRouteNewPageYaml
from testsuite.page_objects.policies.policies import PoliciesPage


class OverviewPage(Navigable):  # pylint: disable=too-many-public-methods
    """Page object for the Kuadrant / RHCL Overview page"""

    def __init__(self, page: Page):
        super().__init__(page)
        # Main page heading that matches both "Kuadrant Overview" and "Connectivity Link Overview"
        self.page_heading = page.locator("h1").filter(has_text="Overview")

    # Page-level methods
    def is_displayed(self):
        """Returns the page heading locator"""
        return self.page_heading

    def page_displayed(self):
        """Check if the overview page is displayed"""
        self.page_heading.wait_for(state="visible", timeout=60000)
        return self.page_heading.is_visible()

    # Getting started resources section methods
    def has_getting_started_section(self):
        """Check if the Getting started resources section is visible"""
        return self.page.get_by_text("Getting started resources").is_visible()

    def has_learning_resources(self):
        """Check if the Learning Resources card is visible"""
        return self.page.get_by_text("Learning Resources").is_visible()

    def has_feature_highlights(self):
        """Check if the Feature Highlights card is visible"""
        return self.page.get_by_text("Feature Highlights").is_visible()

    def has_operations_tools(self):
        """Check if the Operations & Tools card is visible (or 'Enhance Your Work' in 4.19 and below)"""
        return (
            self.page.get_by_text("Operations & Tools").is_visible()
            or self.page.get_by_text("Enhance Your Work").is_visible()
        )

    def has_view_documentation_link(self):
        """Check if the View Documentation link is visible and has correct href"""
        link = self.page.get_by_role("link", name="View Documentation")
        if not link.is_visible():
            return False

        href = link.get_attribute("href")
        kuadrant_pattern = r"^https://docs\.kuadrant\.io$"
        rhcl_pattern = r"^https://docs\.redhat\.com/en/documentation/red_hat_connectivity_link/\d+\.\d+/$"
        return bool(re.match(kuadrant_pattern, href) or re.match(rhcl_pattern, href))

    def has_view_config_and_deploy_link(self):
        """Check if the Configuring and deploying Gateway policies link is visible and has correct href"""
        link = self.page.get_by_role("link").filter(has_text="Configuring and deploying Gateway policies")
        if not link.first.is_visible():
            return False

        href = link.first.get_attribute("href")
        kuadrant_pattern = (
            r"^https://docs\.kuadrant\.io/latest/kuadrant-operator/doc/user-guides/"
            r"full-walkthrough/secure-protect-connect/$"
        )
        rhcl_pattern = (
            r"^https://docs\.redhat\.com/en/documentation/red_hat_connectivity_link/\d+\.\d+/"
            r"html-single/configuring_and_deploying_gateway_policies_with_connectivity_link/index$"
        )
        return bool(re.match(kuadrant_pattern, href) or re.match(rhcl_pattern, href))

    def has_release_notes_link(self):
        """Check if the Release Notes link is visible and has correct href"""
        link = self.page.get_by_role("link").filter(has_text="Release Notes")
        if not link.first.is_visible():
            return False

        href = link.first.get_attribute("href")
        kuadrant_pattern = r"^https://github\.com/Kuadrant/kuadrant-operator/releases$"
        rhcl_pattern = (
            r"^https://docs\.redhat\.com/en/documentation/red_hat_connectivity_link/\d+\.\d+/"
            r"html-single/release_notes_for_connectivity_link_\d+\.\d+/index$"
        )
        return bool(re.match(kuadrant_pattern, href) or re.match(rhcl_pattern, href))

    def has_observability_link(self):
        """Check if the Observability link is visible and has correct href"""
        link = self.page.get_by_role("link").filter(has_text="Observability")
        if not link.first.is_visible():
            return False

        href = link.first.get_attribute("href")
        kuadrant_pattern = r"^https://docs\.kuadrant\.io/latest/kuadrant-operator/doc/observability/examples/$"
        rhcl_pattern = (
            r"^https://docs\.redhat\.com/en/documentation/red_hat_connectivity_link/\d+\.\d+/"
            r"html-single/connectivity_link_observability_guide/index$"
        )
        return bool(re.match(kuadrant_pattern, href) or re.match(rhcl_pattern, href))

    def has_cert_manager_link(self):
        """Check if the cert-manager Operator link is visible and has correct href"""
        link = self.page.get_by_role("link", name="cert-manager Operator")
        if not link.is_visible():
            return False

        href = link.get_attribute("href")
        # Match any namespace (kuadrant, kuadrant-system, etc.)
        pattern = (
            r"^/operatorhub/ns/[^?]+\?keyword=cert-manager&details-item="
            r"openshift-cert-manager-operator-redhat-operators-openshift-marketplace$"
        )
        return bool(re.match(pattern, href))

    # Gateways status section methods
    def has_gateways_section(self):
        """Check if the Gateways status section is visible"""
        return self.page.get_by_role("heading", name="Gateways", exact=True).is_visible()

    def has_total_gateways_metric(self):
        """Check if the Total Gateways metric is visible"""
        return self.page.get_by_text("Total Gateways", exact=True).is_visible()

    def has_healthy_gateways_metric(self):
        """Check if the Healthy Gateways metric is visible"""
        return self.page.get_by_text("Healthy Gateways", exact=True).is_visible()

    def has_unhealthy_gateways_metric(self):
        """Check if the Unhealthy Gateways metric is visible"""
        return self.page.get_by_text("Unhealthy Gateways", exact=True).is_visible()

    def get_total_gateways_count(self):
        """Get the count of total gateways from the metric"""
        metric_card = self.page.locator("//div[contains(., 'Total Gateways')]").first
        count_element = metric_card.locator("strong").first
        return int(count_element.inner_text().strip())

    def get_unhealthy_gateways_count(self):
        """Get the count of unhealthy gateways from the metric"""
        metric_card = self.page.locator("//div[contains(., 'Unhealthy Gateways')]").first
        count_element = metric_card.locator("strong").first
        return int(count_element.inner_text().strip())

    def get_healthy_gateways_count(self):
        """Get the count of healthy gateways from the metric"""
        metric_card = self.page.locator("//div[contains(., 'Healthy Gateways')]").first
        count_element = metric_card.locator("strong").first
        return int(count_element.inner_text().strip())

    def wait_for_healthy_gateways(self, expected_count: int, timeout: int = 60000):
        """Wait for the healthy gateways count to reach at least the expected value"""
        retries = timeout // 2000  # Number of 2-second intervals
        for _ in range(retries):
            try:
                if self.get_healthy_gateways_count() >= expected_count:
                    return True
            except (PlaywrightTimeoutError, ValueError):
                pass
            self.page.wait_for_timeout(2000)
        return False

    # Gateways - Traffic Analysis section methods
    def has_gateways_traffic_section(self):
        """Check if the Gateways - Traffic Analysis section is visible"""
        return self.page.get_by_role("heading", name="Gateways - Traffic Analysis", exact=True).is_visible()

    @step(GatewayNewPageYaml)
    def new_gateway(self):
        """Click Create Gateway button"""
        self.page.get_by_text("Create Gateway").click()

    def has_gateway_in_traffic_analysis(self, gateway_name: str):
        """Check if gateway appears in traffic analysis section"""
        # Wait a moment for the gateway to appear after creation
        self.page.wait_for_timeout(3000)
        locator = self.page.locator(f"//tr//a[@data-test-id='{gateway_name}']")
        return locator.count() > 0

    def click_gateway(self, gateway_name: str):
        """Click on a gateway name to navigate to its details page"""
        self.page.get_by_role("link", name=gateway_name).click()

    # Policies section methods
    def has_policies_section(self):
        """Check if the Policies section is visible"""
        return self.page.get_by_role("heading", name="Policies", exact=True).is_visible()

    @step(PoliciesPage)
    def new_policy(self):
        """Click Create Policy button"""
        self.page.get_by_text("Create Policy").click()

    def has_policy_in_section(self, policy_name: str):
        """Check if policy appears in section"""
        self.page.wait_for_timeout(3000)
        locator = self.page.locator(f"//tr//a[@data-test-id='{policy_name}']")
        return locator.count() > 0

    def click_policy(self, policy_name: str):
        """Click on a policy name to navigate to its details page"""
        self.page.get_by_role("link", name=policy_name).click()

    # HTTPRoutes section methods
    def has_httproute_section(self):
        """Check if the HTTPRoutes section is visible"""
        return self.page.get_by_role("heading", name="HTTPRoutes", exact=True).is_visible()

    @step(HTTPRouteNewPageYaml)
    def new_httproute(self):
        """Click Create HTTPRoute button"""
        self.page.get_by_text("Create HTTPRoute").click()

    def has_httproute_in_section(self, httproute_name: str):
        """Check if HTTPRoute appears in section"""
        self.page.wait_for_timeout(3000)
        locator = self.page.locator(f"//tr//a[@data-test-id='{httproute_name}']")
        return locator.count() > 0

    def click_httproute(self, httproute_name: str):
        """Click on an HTTPRoute name to navigate to its details page"""
        self.page.get_by_role("link", name=httproute_name).click()

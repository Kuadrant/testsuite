"""Policies landing page for the console plugin"""

from testsuite.page_objects.policies.auth_policy import AuthListPage
from testsuite.page_objects.navigator import step, Navigable
from testsuite.page_objects.policies.dns_policy import DNSListPage
from testsuite.page_objects.policies.rate_limit_policy import RateLimitListPage
from testsuite.page_objects.policies.tls_policy import TLSListPage
from testsuite.page_objects.policies.token_rate_limit import TokenRateLimitListPage
from testsuite.page_objects.policies.oidc_policy import OIDCPolicyListPage
from testsuite.page_objects.policies.plan_policy import PlanPolicyListPage


class PoliciesPage(Navigable):
    """Page object for the Policies overview page with tabs for each policy type"""

    def __init__(self, page):
        super().__init__(page)
        self.dns_tab = self.page.locator("//a[@data-test-id='horizontal-link-DNS']")
        self.tls_tab = self.page.locator("//a[@data-test-id='horizontal-link-TLS']")
        self.auth_tab = self.page.locator("//a[@data-test-id='horizontal-link-Auth']")
        self.rate_limit_tab = self.page.locator("//a[@data-test-id='horizontal-link-RateLimit']")
        self.token_rate_limit_tab = self.page.locator("//a[@data-test-id='horizontal-link-TokenRateLimit']")
        self.oidc_tab = self.page.locator("//a[@data-test-id='horizontal-link-OIDC']")
        self.plan_tab = self.page.locator("//a[@data-test-id='horizontal-link-Plan']")

    @step(DNSListPage)
    def dns(self):
        """Navigates to the DNSPolicy list page and returns a DNSListPage object"""
        self.dns_tab.click()

    @step(TLSListPage)
    def tls(self):
        """Navigates to the TLSPolicy list page and returns a TLSListPage object"""
        self.tls_tab.click()

    @step(AuthListPage)
    def auth(self):
        """Navigates to the AuthPolicy list page and returns an AuthListPage object"""
        self.auth_tab.click()

    @step(RateLimitListPage)
    def rate_limit(self):
        """Navigates to the RateLimitPolicy list page and returns a RateLimitListPage object"""
        self.rate_limit_tab.click()

    @step(TokenRateLimitListPage)
    def token_rate_limit(self):
        """Navigates to the TokenRateLimitPolicy list page and returns a TokenRateLimitListPage object"""
        self.token_rate_limit_tab.click()

    @step(OIDCPolicyListPage)
    def oidc(self):
        """Navigates to the OIDCPolicy list page and returns an OIDCPolicyListPage object"""
        self.oidc_tab.click()

    @step(PlanPolicyListPage)
    def plan(self):
        """Navigates to the PlanPolicy list page and returns a PlanPolicyListPage object"""
        self.plan_tab.click()

    def is_displayed(self):
        """Returns all policy tab locators"""
        return (
            self.dns_tab,
            self.tls_tab,
            self.auth_tab,
            self.rate_limit_tab,
            self.token_rate_limit_tab,
            self.oidc_tab,
            self.plan_tab,
        )

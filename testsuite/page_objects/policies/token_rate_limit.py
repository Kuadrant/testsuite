"""Page objects for interacting with TokenRateLimitPolicy creation and list views in the console plugin UI"""

from testsuite.page_objects.navigator import step
from testsuite.page_objects.policies.policies_new_page import BasePolicyNewPageYaml
from testsuite.page_objects.policies.policies_list_page import BasePolicyListPage
from testsuite.tests.singlecluster.ui.console_plugin.constants import UI_PAGE_LOAD_TIMEOUT


class TokenRateLimitPolicyType:
    """Provides the policy_type for TokenRateLimitPolicy pages"""

    @property
    def policy_type(self) -> str:
        """Returns the policy type name"""
        return "TokenRateLimitPolicy"

    @property
    def policy_url_path(self) -> str:
        """Returns the console URL path for TokenRateLimitPolicy (uses v1alpha1)"""
        return "kuadrant.io~v1alpha1~TokenRateLimitPolicy"


class TokenRateLimitNewPageYaml(TokenRateLimitPolicyType, BasePolicyNewPageYaml):
    """Page object for creating a new TokenRateLimitPolicy using YAML editor"""

    check_enforcement = False

    def page_displayed(self):
        """Check if the TokenRateLimitPolicy YAML creation page is displayed"""
        self.editor.wait_for(state="visible", timeout=UI_PAGE_LOAD_TIMEOUT)
        return self.editor.is_visible() and self.create_btn.is_visible()


class TokenRateLimitListPage(TokenRateLimitPolicyType, BasePolicyListPage):
    """Page object for listing and managing TokenRateLimitPolicies"""

    @step(TokenRateLimitNewPageYaml)
    def new(self):
        """Click the Create TokenRateLimitPolicy button"""
        self.new_btn.click()

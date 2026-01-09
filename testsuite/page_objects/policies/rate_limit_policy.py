"""Page objects for interacting with RateLimitPolicy creation and list views in the console plugin UI"""

from testsuite.page_objects.navigator import step
from testsuite.page_objects.policies.policies_new_page import BasePolicyNewPageYaml
from testsuite.page_objects.policies.policies_list_page import BasePolicyListPage


class RateLimitPolicyType:
    """Provides the policy_type for RateLimitPolicy pages"""

    @property
    def policy_type(self) -> str:
        """Returns the policy type name"""
        return "RateLimitPolicy"


class RateLimitNewPageYaml(RateLimitPolicyType, BasePolicyNewPageYaml):
    """Page object for creating a new RateLimitPolicy using YAML editor"""

    def page_displayed(self):
        """Check if the RateLimitPolicy YAML creation page is displayed"""
        self.editor.wait_for(state="visible", timeout=60000)
        return self.editor.is_visible() and self.create_btn.is_visible()


class RateLimitListPage(RateLimitPolicyType, BasePolicyListPage):
    """Page object for listing and managing RateLimitPolicies"""

    @step(RateLimitNewPageYaml)
    def new(self):
        """Click the Create RateLimitPolicy button"""
        self.new_btn.click()

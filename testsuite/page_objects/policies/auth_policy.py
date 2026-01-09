"""Page objects for interacting with AuthPolicy creation and list views in the console plugin UI"""

from testsuite.page_objects.navigator import step
from testsuite.page_objects.policies.policies_new_page import BasePolicyNewPageYaml
from testsuite.page_objects.policies.policies_list_page import BasePolicyListPage


class AuthPolicyType:
    """Provides the policy_type for AuthPolicy pages"""

    @property
    def policy_type(self) -> str:
        """Returns the policy type name"""
        return "AuthPolicy"


class AuthNewPageYaml(AuthPolicyType, BasePolicyNewPageYaml):
    """Page object for creating a new AuthPolicy using YAML editor"""

    def page_displayed(self):
        """Check if the AuthPolicy YAML creation page is displayed"""
        self.editor.wait_for(state="visible", timeout=60000)
        return self.editor.is_visible() and self.create_btn.is_visible()


class AuthListPage(AuthPolicyType, BasePolicyListPage):
    """Page object for listing and managing AuthPolicies"""

    @step(AuthNewPageYaml)
    def new(self):
        """Click the Create AuthPolicy button"""
        self.new_btn.click()

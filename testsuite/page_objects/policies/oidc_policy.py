"""Page objects for interacting with OIDCPolicy creation and list views in the console plugin UI"""

from testsuite.page_objects.navigator import step
from testsuite.page_objects.policies.policies_new_page import BasePolicyNewPageYaml
from testsuite.page_objects.policies.policies_list_page import BasePolicyListPage
from testsuite.tests.singlecluster.ui.console_plugin.constants import UI_PAGE_LOAD_TIMEOUT


class OIDCPolicyType:
    """Provides the policy_type for OIDCPolicy pages"""

    @property
    def policy_type(self) -> str:
        """Returns the policy type name"""
        return "OIDCPolicy"

    @property
    def policy_url_path(self) -> str:
        """Returns the console URL path for OIDCPolicy (uses extensions.kuadrant.io)"""
        return "extensions.kuadrant.io~v1alpha1~OIDCPolicy"


class OIDCPolicyNewPageYaml(OIDCPolicyType, BasePolicyNewPageYaml):
    """Page object for creating a new OIDCPolicy using YAML editor"""

    check_enforcement = False

    def page_displayed(self):
        """Check if the OIDCPolicy YAML creation page is displayed"""
        self.editor.wait_for(state="visible", timeout=UI_PAGE_LOAD_TIMEOUT)
        return self.editor.is_visible() and self.create_btn.is_visible()


class OIDCPolicyListPage(OIDCPolicyType, BasePolicyListPage):
    """Page object for listing and managing OIDCPolicies"""

    @step(OIDCPolicyNewPageYaml)
    def new(self):
        """Click the Create OIDCPolicy button"""
        self.new_btn.click()

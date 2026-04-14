"""Page objects for interacting with PlanPolicy creation and list views in the console plugin UI"""

from testsuite.page_objects.navigator import step
from testsuite.page_objects.policies.policies_new_page import BasePolicyNewPageYaml
from testsuite.page_objects.policies.policies_list_page import BasePolicyListPage
from testsuite.tests.singlecluster.ui.console_plugin.constants import UI_PAGE_LOAD_TIMEOUT


class PlanPolicyType:
    """Provides the policy_type for PlanPolicy pages"""

    @property
    def policy_type(self) -> str:
        """Returns the policy type name"""
        return "PlanPolicy"

    @property
    def policy_url_path(self) -> str:
        """Returns the console URL path for PlanPolicy (uses extensions.kuadrant.io)"""
        return "extensions.kuadrant.io~v1alpha1~PlanPolicy"


class PlanPolicyNewPageYaml(PlanPolicyType, BasePolicyNewPageYaml):
    """Page object for creating a new PlanPolicy using YAML editor"""

    check_enforcement = False

    def page_displayed(self):
        """Check if the PlanPolicy YAML creation page is displayed"""
        self.editor.wait_for(state="visible", timeout=UI_PAGE_LOAD_TIMEOUT)
        return self.editor.is_visible() and self.create_btn.is_visible()


class PlanPolicyListPage(PlanPolicyType, BasePolicyListPage):
    """Page object for listing and managing PlanPolicies"""

    @step(PlanPolicyNewPageYaml)
    def new(self):
        """Click the Create PlanPolicy button"""
        self.new_btn.click()

"""Page objects for interacting with TLSPolicy creation and list views in the console plugin UI"""

from playwright.sync_api import Page

from testsuite.kuadrant.policy.tls import TLSPolicy
from testsuite.page_objects.navigator import step
from testsuite.page_objects.policies.policies_new_page import BasePolicyNewPageForm, BasePolicyNewPageYaml
from testsuite.page_objects.policies.policies_list_page import BasePolicyListPage


class TLSPolicyType:
    """Provides the policy_type for TLSPolicy pages"""

    @property
    def policy_type(self) -> str:
        """Returns the policy type name"""
        return "TLSPolicy"


class TLSNewPageYaml(TLSPolicyType, BasePolicyNewPageYaml):
    """Page object for creating a new TLSPolicy using YAML editor"""

    def page_displayed(self):
        """Check if the TLSPolicy creation page is displayed (starts in Form view)"""
        self.page.locator("text=Create TLS Policy").wait_for(state="visible", timeout=60000)
        return True


class TLSNewPageForm(TLSPolicyType, BasePolicyNewPageForm):
    """Page object for creating a new TLSPolicy using the form"""

    def __init__(self, page: Page):
        super().__init__(page)
        self.policy_name = self.page.locator("//input[@id='simple-form-policy-name-01']")
        self.gateway_select = self.page.locator("//select[@id='gateway-select']")
        self.cluster_issuer_checkbox = self.page.locator("//input[@id='cluster-issuer']")
        self.issuer_checkbox = self.page.locator("//input[@id='issuer']")
        self.cluster_issuer_select = self.page.locator("//select[@id='clusterissuer-select']")
        self.create_button = self.page.get_by_text("Create", exact=True)

    def create(self, policy: TLSPolicy):
        """Fill the form and create the TLSPolicy"""
        # Get namespace from the policy metadata
        namespace = policy.model.metadata.namespace

        # Switch namespace and navigate to form
        self._switch_namespace_and_navigate_to_form(namespace)

        # Fill common fields (name and target ref)
        self._fill_common_fields(policy)

        # Choose the issuer type (ClusterIssuer or Issuer)
        issuer_kind = policy.model.spec.get("issuerRef", {}).get("kind", "")
        if issuer_kind == "ClusterIssuer":
            self.cluster_issuer_checkbox.check()
        else:
            self.issuer_checkbox.check()

        # Select the specific issuer name
        issuer_name = policy.model.spec.get("issuerRef", {}).get("name", "")
        self.cluster_issuer_select.select_option(issuer_name)

        # Wait for Create button to enable and click to submit
        self._wait_and_click_create()

    def is_displayed(self):
        """Returns key form field locators"""
        return self.policy_name, self.gateway_select, self.cluster_issuer_select

    def page_displayed(self):
        """Check if the TLSPolicy form creation page is displayed"""
        self.page.locator("text=Create TLS Policy").wait_for(state="visible", timeout=60000)
        return True


class TLSListPage(TLSPolicyType, BasePolicyListPage):
    """Page object for listing and managing TLSPolicies"""

    @step(TLSNewPageForm)
    def new_form(self):
        """Click the Create TLSPolicy button and go to form view"""
        self.new_btn.click()

    @step(TLSNewPageYaml)
    def new_yaml(self):
        """Click the Create TLSPolicy button and go to YAML view"""
        self.new_btn.click()

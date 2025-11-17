"""Page objects for interacting with DNSPolicy creation and list views in the console plugin UI"""

from playwright.sync_api import Page

from testsuite.kuadrant.policy.dns import DNSPolicy
from testsuite.page_objects.navigator import step
from testsuite.page_objects.policies.policies_new_page import BasePolicyNewPageForm, BasePolicyNewPageYaml
from testsuite.page_objects.policies.policies_list_page import BasePolicyListPage


class DNSPolicyType:
    """Provides the policy_type for DNSPolicy pages"""

    @property
    def policy_type(self) -> str:
        """Returns the policy type name"""
        return "DNSPolicy"


class DNSNewPageYaml(DNSPolicyType, BasePolicyNewPageYaml):
    """Page object for creating a new DNSPolicy using YAML editor"""

    def page_displayed(self):
        """Check if the DNSPolicy creation page is displayed (starts in Form view)"""
        self.page.locator("text=Create DNS Policy").wait_for(state="visible", timeout=60000)
        return True


class DNSNewPageForm(DNSPolicyType, BasePolicyNewPageForm):
    """Page object for creating a new DNSPolicy using the form"""

    def __init__(self, page: Page):
        super().__init__(page)
        self.policy_name = self.page.locator("//input[@id='policy-name']")
        self.gateway_select = self.page.locator("//select[@id='gateway-select']")
        self.provider_ref_input = self.page.locator("//input[@id='provider-ref']")
        self.weight_input = self.page.locator("//input[@id='weight']")
        self.geo_input = self.page.locator("//input[@id='geo']")
        self.create_button = self.page.get_by_text("Create", exact=True)

    def create(self, policy: DNSPolicy):
        """Fill the form and create the DNSPolicy"""
        # Get namespace from the policy metadata
        namespace = policy.model.metadata.namespace

        # Switch namespace and navigate to form
        self._switch_namespace_and_navigate_to_form(namespace)

        # Fill common fields (name and target ref)
        self._fill_common_fields(policy)

        # Fill the provider reference if present
        provider_refs = policy.model.spec.get("providerRefs", [])
        if provider_refs:
            self.provider_ref_input.fill(provider_refs[0].get("name", ""))

        # Expand and fill LoadBalancing section
        load_balancing_section = self.page.get_by_text("LoadBalancing")
        load_balancing_section.click()
        self.page.wait_for_selector("//input[@id='weight']", timeout=10000)

        lb_spec = policy.model.spec.get("loadBalancing", {})
        self.weight_input.fill(str(lb_spec.get("weight", 100)))
        self.geo_input.fill(lb_spec.get("geo", "EU"))

        # Select the defaultGeo option
        if lb_spec.get("defaultGeo", False):
            self.page.locator("//input[@id='default-geo-enabled']").check()
        else:
            self.page.locator("//input[@id='default-geo-disabled']").check()

        # Wait for Create button to enable and click to submit
        self._wait_and_click_create()

    def is_displayed(self):
        """Returns key form field locators"""
        return self.policy_name, self.gateway_select, self.provider_ref_input, self.weight_input

    def page_displayed(self):
        """Check if the DNSPolicy form creation page is displayed"""
        self.page.locator("text=Create DNS Policy").wait_for(state="visible", timeout=60000)
        return True


class DNSListPage(DNSPolicyType, BasePolicyListPage):
    """Page object for listing and managing DNSPolicies"""

    @step(DNSNewPageForm)
    def new_form(self):
        """Click the Create DNSPolicy button and go to form view"""
        self.new_btn.click()

    @step(DNSNewPageYaml)
    def new_yaml(self):
        """Click the Create DNSPolicy button and go to YAML view"""
        self.new_btn.click()

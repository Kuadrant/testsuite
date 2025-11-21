"""Page objects for interacting with DNSPolicy creation and list views in the console plugin UI"""

from playwright.sync_api import Page
import yaml
from testsuite.kuadrant.policy.dns import DNSPolicy
from testsuite.page_objects.navigator import Navigable, step
from testsuite.page_objects.policies.policies_list_page import BasePolicyListPage
from testsuite.config import settings


class DNSNewPage(Navigable):  # pylint: disable=too-many-instance-attributes
    """Page object for creating a new DNSPolicy"""

    def __init__(self, page: Page):
        super().__init__(page)
        # Form
        self.policy_name = self.page.locator("//input[@id='policy-name']")
        self.gateway_select = self.page.locator("//select[@id='gateway-select']")
        self.provider_ref_input = self.page.locator("//input[@id='provider-ref']")
        self.weight_input = self.page.locator("//input[@id='weight']")
        self.geo_input = self.page.locator("//input[@id='geo']")
        self.create_button = self.page.get_by_text("Create", exact=True)

        # Yaml
        self.editor = page.locator("div.monaco-editor[data-uri]").first
        self.create_btn = page.locator("#save-changes")

    def create_form(self, dns_policy: DNSPolicy):
        """Fill the form and create the DNSPolicy"""

        # Get namespace from settings
        namespace = settings["service_protection"]["project"]

        # Switch namespace from 'default' to the configured namespace in the console project selector
        project_selector = self.page.locator("//button[contains(., 'Project:')]")
        project_selector.click()
        self.page.get_by_role("menuitem", name=namespace).first.click()

        # Navigate back to the form page in the correct namespace
        if "/form" not in self.page.url:
            # Construct the proper form URL with the configured namespace
            base_url = self.page.url.split("/k8s/")[0]
            form_url = f"{base_url}/k8s/ns/{namespace}/kuadrant.io~v1~DNSPolicy/~new/form"
            self.page.goto(form_url)

        # Wait for form to be visible
        self.policy_name.wait_for(state="visible")

        # Fill the policy name field
        self.policy_name.fill(dns_policy.model.metadata.name)

        # Select the target Gateway from the dropdown
        target_ref_name = dns_policy.model.spec.get("targetRef", {}).get("name", "")
        self.gateway_select.select_option(value=f"{namespace}/{target_ref_name}")

        # Fill the provider reference if present
        provider_refs = dns_policy.model.spec.get("providerRefs", [])
        if provider_refs:
            self.provider_ref_input.fill(provider_refs[0].get("name", ""))

        # Expand and fill LoadBalancing section first
        load_balancing_section = self.page.get_by_text("LoadBalancing")
        load_balancing_section.click()
        self.page.wait_for_selector("//input[@id='weight']", timeout=10000)

        lb_spec = dns_policy.model.spec.get("loadBalancing", {})
        self.weight_input.fill(str(lb_spec.get("weight", 100)))
        self.geo_input.fill(lb_spec.get("geo", "EU"))

        # Select the defaultGeo option
        if lb_spec.get("defaultGeo", False):
            self.page.locator("//input[@id='default-geo-enabled']").check()
        else:
            self.page.locator("//input[@id='default-geo-disabled']").check()

        # Wait for Create button to enable and click to submit
        self.page.wait_for_selector("button:has-text('Create'):not([disabled])")
        self.create_button.scroll_into_view_if_needed()
        self.create_button.click()

    def create_yaml(self, dns_policy: DNSPolicy):
        """Fill the YAML editor and create the DNSPolicy"""

        # Switch to YAML view
        yaml_view_radio = self.page.locator("//input[@id='create-type-radio-yaml']")
        yaml_view_radio.wait_for(state="visible", timeout=10000)
        yaml_view_radio.check()

        # Wait for the YAML editor to be visible
        self.editor.wait_for(state="visible")

        # Set the namespace and convert the policy object to YAML
        dns_policy.model.metadata.namespace = settings["service_protection"]["project"]
        yaml_text = yaml.safe_dump(dns_policy.as_dict(), sort_keys=False)

        # Inject YAML directly into the Monaco editor
        self.page.evaluate(
            """(yaml) => {
                const editor = window.monaco?.editor?.getModels?.()[0];
                if (editor) editor.setValue(yaml);
            }""",
            yaml_text,
        )

        # Wait until the Create button becomes enabled
        self.page.wait_for_selector("#save-changes:not([disabled])")

        # Click Create to submit the policy
        self.create_btn.scroll_into_view_if_needed()
        self.create_btn.click()

        # Wait for the details page to load and display confirmation
        self.page.wait_for_selector("text=DNSPolicy details")
        self.page.wait_for_selector("text=DNSPolicy has been accepted", timeout=60000)

    def is_displayed(self):
        """Returns key form field locators"""
        return self.policy_name, self.gateway_select, self.provider_ref_input, self.weight_input


class DNSListPage(BasePolicyListPage):
    """Page object for listing and managing DNSPolicies"""

    @property
    def policy_type(self) -> str:
        return "DNSPolicy"

    @property
    def policy_url_path(self) -> str:
        return "kuadrant.io~v1~DNSPolicy"

    @step(DNSNewPage)
    def new(self):
        """Click the Create DNSPolicy button"""
        self.new_btn.click()

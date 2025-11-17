"""Page objects for interacting with TLSPolicy creation and list views in the console plugin UI"""

import yaml
from playwright.sync_api import Page

from testsuite.kuadrant.policy.tls import TLSPolicy
from testsuite.page_objects.navigator import Navigable, step
from testsuite.page_objects.policies.policies_list_page import BasePolicyListPage


class TLSNewPage(Navigable):  # pylint: disable=too-many-instance-attributes
    """Page object for creating a new TLSPolicy"""

    def __init__(self, page: Page):
        super().__init__(page)
        # Form
        self.policy_name = self.page.locator("//input[@id='simple-form-policy-name-01']")
        self.gateway_select = self.page.locator("//select[@id='gateway-select']")
        self.cluster_issuer_checkbox = self.page.locator("//input[@id='cluster-issuer']")
        self.issuer_checkbox = self.page.locator("//input[@id='issuer']")
        self.cluster_issuer_select = self.page.locator("//select[@id='clusterissuer-select']")
        self.create_button = self.page.get_by_text("Create", exact=True)

        # Yaml
        self.editor = page.locator("div.monaco-editor[data-uri]").first
        self.create_btn = page.locator("#save-changes")

    def create_form(self, tls_policy: TLSPolicy):
        """Fill the form and create the TLSPolicy"""

        # Get namespace from the policy metadata
        namespace = tls_policy.model.metadata.namespace

        # Switch namespace from 'default' to the configured namespace
        project_selector = self.page.locator("//button[contains(., 'Project:')]")
        project_selector.click()
        self.page.get_by_role("menuitem", name=namespace).first.click()

        # Navigate back to the form page in the correct namespace
        if "/form" not in self.page.url:
            # Construct the proper form URL with the configured namespace
            base_url = self.page.url.split("/k8s/")[0]
            form_url = f"{base_url}/k8s/ns/{namespace}/kuadrant.io~v1~TLSPolicy/~new/form"
            self.page.goto(form_url)

        # Wait for form to be visible
        self.policy_name.wait_for(state="visible")

        # Fill the policy name field
        self.policy_name.fill(tls_policy.model.metadata.name)

        # Select the target Gateway from the dropdown
        target_ref_name = tls_policy.model.spec.get("targetRef", {}).get("name", "")
        self.gateway_select.select_option(value=f"{namespace}/{target_ref_name}")

        # Choose the issuer type (ClusterIssuer or Issuer)
        issuer_kind = tls_policy.model.spec.get("issuerRef", {}).get("kind", "")
        if issuer_kind == "ClusterIssuer":
            self.cluster_issuer_checkbox.check()
        else:
            self.issuer_checkbox.check()

        # Select the specific issuer name
        issuer_name = tls_policy.model.spec.get("issuerRef", {}).get("name", "")
        self.cluster_issuer_select.select_option(issuer_name)

        # Wait for Create button to enable and click to submit
        self.page.wait_for_selector("button:has-text('Create'):not([disabled])")
        self.create_button.scroll_into_view_if_needed()
        self.create_button.click()

    def create_yaml(self, tls_policy: TLSPolicy):
        """Fill the YAML editor and create the TLSPolicy"""

        # Switch to YAML view
        yaml_view_radio = self.page.locator("//input[@id='yaml-view']")
        yaml_view_radio.wait_for(state="visible", timeout=10000)
        yaml_view_radio.check()

        # Wait for the YAML editor to be visible
        self.editor.wait_for(state="visible")

        # Convert the policy object to YAML
        yaml_text = yaml.safe_dump(tls_policy.as_dict(), sort_keys=False)

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
        self.page.wait_for_selector("text=TLSPolicy details")
        self.page.wait_for_selector("text=TLSPolicy has been accepted", timeout=60000)
        self.page.wait_for_selector("text=TLSPolicy has been successfully enforced", timeout=60000)

    def is_displayed(self):
        """Returns key form field locators"""
        return self.policy_name, self.gateway_select, self.cluster_issuer_select

    def page_displayed(self):
        """Check if the TLSPolicy creation page is displayed"""
        # Check for an element that's always visible regardless of form/yaml view
        self.page.locator("text=Create TLS Policy").wait_for(state="visible", timeout=60000)
        return True


class TLSListPage(BasePolicyListPage):
    """Page object for listing and managing TLSPolicies"""

    @property
    def policy_type(self) -> str:
        return "TLSPolicy"

    @step(TLSNewPage)
    def new(self):
        """Click the Create TLSPolicy button"""
        self.new_btn.click()

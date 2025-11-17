"""Base classes for policy creation pages"""

from abc import abstractmethod
import yaml
from playwright.sync_api import Page
from testsuite.page_objects.navigator import Navigable


class BasePolicyNewPage(Navigable):
    """Base class for policy creation pages"""

    @abstractmethod
    def create(self, policy):
        """Create the policy using the page's specific method (form or YAML)"""

    @abstractmethod
    def page_displayed(self):
        """Check if the policy creation page is displayed"""


class BasePolicyNewPageYaml(BasePolicyNewPage):
    """Base class for YAML-based policy creation pages"""

    def __init__(self, page: Page):
        super().__init__(page)
        self.editor = page.locator("div.monaco-editor[data-uri]").first
        self.create_btn = page.locator("#save-changes")

    @property
    @abstractmethod
    def policy_type(self) -> str:
        """Returns the policy type name (e.g., 'DNSPolicy', 'AuthPolicy')"""

    def create(self, policy):
        """Fill the YAML editor and create the policy"""
        # Switch to YAML view if needed (some pages default to form view)
        yaml_view_radio = self.page.locator("//input[@id='create-type-radio-yaml' or @id='yaml-view']")
        if yaml_view_radio.count() > 0 and yaml_view_radio.is_visible():
            yaml_view_radio.check()

        # Wait for the YAML editor to be visible
        self.editor.wait_for(state="visible")

        # Convert the policy object to YAML
        yaml_text = yaml.safe_dump(policy.as_dict(), sort_keys=False)

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
        self.page.wait_for_selector(f"text={self.policy_type} details")
        self.page.wait_for_selector(f"text={self.policy_type} has been accepted", timeout=60000)
        self.page.wait_for_selector(f"text={self.policy_type} has been successfully enforced", timeout=60000)

    def is_displayed(self):
        """Returns the editor and create button locators"""
        return self.editor, self.create_btn


class BasePolicyNewPageForm(BasePolicyNewPage):
    """Base class for form-based policy creation pages"""

    def __init__(self, page: Page):
        super().__init__(page)
        self.policy_name = None
        self.gateway_select = None
        self.create_button = None

    @property
    @abstractmethod
    def policy_type(self) -> str:
        """Returns the policy type name for URL construction"""

    def _switch_namespace_and_navigate_to_form(self, namespace):
        """Helper method to switch namespace and navigate to the form page"""
        # Switch namespace from 'default' to the configured namespace
        project_selector = self.page.locator("//button[contains(., 'Project:')]")
        project_selector.click()
        self.page.get_by_role("menuitem", name=namespace).first.click()

        # Navigate to the form page in the correct namespace
        if "/form" not in self.page.url:
            base_url = self.page.url.split("/k8s/")[0]
            form_url = f"{base_url}/k8s/ns/{namespace}/kuadrant.io~v1~{self.policy_type}/~new/form"
            self.page.goto(form_url)

    def _fill_common_fields(self, policy):
        """Helper method to fill common form fields (name and target ref)"""
        # Wait for form to be visible
        self.policy_name.wait_for(state="visible")

        # Fill the policy name field
        self.policy_name.fill(policy.model.metadata.name)

        # Select the target Gateway from the dropdown
        namespace = policy.model.metadata.namespace
        target_ref_name = policy.model.spec.get("targetRef", {}).get("name", "")
        self.gateway_select.select_option(value=f"{namespace}/{target_ref_name}")

    def _wait_and_click_create(self):
        """Helper method to wait for Create button to be enabled and click it"""
        self.page.wait_for_selector("button:has-text('Create'):not([disabled])")
        self.create_button.scroll_into_view_if_needed()
        self.create_button.click()

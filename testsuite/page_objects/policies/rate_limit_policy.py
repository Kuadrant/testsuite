"""Page objects for interacting with RateLimitPolicy creation and list views in the console plugin UI"""

from playwright.sync_api import Page
import yaml
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy
from testsuite.page_objects.navigator import Navigable, step
from testsuite.page_objects.policies.policies_list_page import BasePolicyListPage
from testsuite.config import settings


class RateLimitNewPage(Navigable):
    """Page object for creating a new RateLimitPolicy"""

    def __init__(self, page: Page):
        super().__init__(page)
        self.editor = page.locator("div.monaco-editor[data-uri]").first
        self.create_btn = page.locator("#save-changes")

    def create(self, rate_limit_policy: RateLimitPolicy):
        """Fill the YAML editor and create the RateLimitPolicy"""

        # Wait for the YAML editor to be visible
        self.editor.wait_for(state="visible")

        # Set the namespace and convert the policy object to YAML
        rate_limit_policy.model.metadata.namespace = settings["service_protection"]["project"]
        yaml_text = yaml.safe_dump(rate_limit_policy.as_dict(), sort_keys=False)

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
        self.page.wait_for_selector("text=RateLimitPolicy details")
        self.page.wait_for_selector("text=RateLimitPolicy has been accepted", timeout=60000)

    def is_displayed(self):
        """Returns the editor and create button locators"""
        return self.editor, self.create_btn


class RateLimitListPage(BasePolicyListPage):
    """Page object for listing and managing RateLimitPolicies"""

    @property
    def policy_type(self) -> str:
        return "RateLimitPolicy"

    @property
    def policy_url_path(self) -> str:
        return "kuadrant.io~v1~RateLimitPolicy"

    @step(RateLimitNewPage)
    def new(self):
        """Click the Create RateLimitPolicy button"""
        self.new_btn.click()

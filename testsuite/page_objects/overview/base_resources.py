"""Base class for overview resource pages (creation and details)"""

from abc import abstractmethod
from playwright.sync_api import Page
from testsuite.page_objects.navigator import Navigable


class BaseResourceNewPageYaml(Navigable):
    """Base class for overview resource pages"""

    def __init__(self, page: Page):
        super().__init__(page)
        self.editor = page.locator("div.monaco-editor[data-uri]").first
        self.create_btn = page.locator("#save-changes")

    @property
    @abstractmethod
    def resource_type(self) -> str:
        """Returns the resource type name (e.g., 'Gateway', 'HTTPRoute')"""

    def is_displayed(self):
        """Returns the editor and create button locators"""
        return self.editor, self.create_btn

    def page_displayed(self):
        """Check if the resource YAML creation page is displayed"""
        self.editor.wait_for(state="visible", timeout=60000)
        return self.editor.is_visible() and self.create_btn.is_visible()

    def delete(self):
        """Delete the specified resource via the three dots action button and confirm deletion"""
        # Open the Actions dropdown menu (three dots)
        actions_btn = self.page.locator("//button[contains(., 'Actions')]")
        actions_btn.wait_for(state="visible", timeout=10000)
        actions_btn.click()

        # Find and click the Delete action (supports PF v5 and v6)
        delete_button = self.page.locator(
            f"//button[@data-test-action='Delete {self.resource_type}'] | "
            f"//button[@role='menuitem' and contains(., 'Delete {self.resource_type}')] | "
            "//li[@data-test-action='Delete']"
        ).first
        delete_button.wait_for(state="visible", timeout=10000)
        delete_button.click()

        # Confirm the deletion in the confirmation dialog
        confirm_delete_btn = self.page.locator("//button[@data-test='confirm-action']")
        confirm_delete_btn.wait_for(state="visible", timeout=10000)
        confirm_delete_btn.click()

        # Wait for deletion to complete
        self.page.wait_for_timeout(2000)

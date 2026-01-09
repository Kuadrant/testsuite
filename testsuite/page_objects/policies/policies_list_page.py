"""Base class for policy list pages"""

from abc import abstractmethod
from playwright.sync_api import Page
from testsuite.page_objects.navigator import Navigable


class BasePolicyListPage(Navigable):
    """Base page object for listing and managing policies"""

    def __init__(self, page: Page):
        super().__init__(page)
        self.new_btn = page.get_by_text(f"Create {self.policy_type}")

    @property
    @abstractmethod
    def policy_type(self) -> str:
        """Returns the policy type name (e.g., 'DNSPolicy', 'AuthPolicy')"""

    @property
    def policy_url_path(self) -> str:
        """Returns the console URL path for the policy type (e.g., 'kuadrant.io~v1~DNSPolicy')"""
        return f"kuadrant.io~v1~{self.policy_type}"

    def has_policy(self, name: str) -> bool:
        """Returns True if a policy with the given name appears in the list"""
        # Wait a moment for the list to fully load, but don't require rows to exist
        self.page.wait_for_timeout(10000)
        locator = self.page.locator(f"//tr//a[@data-test-id='{name}']")
        return locator.count() > 0

    def is_policy_listed(self, name: str) -> bool:
        """Searches all paginated list pages and returns True if the policy appears"""
        prev_button = self.page.locator("button[data-action='previous'][aria-label='Go to previous page']")
        next_button = self.page.locator("button[data-action='next'][aria-label='Go to next page']")

        # Ensure we start on the first page
        while prev_button.is_visible() and prev_button.is_enabled():
            prev_button.click()

        # Scan each page until policy found or no more pages left
        while True:
            if self.has_policy(name):
                return True
            # Stop if there is no next page
            if not (next_button.is_visible() and next_button.is_enabled()):
                break
            next_button.click()

        return False

    def delete(self, name: str):
        """Deletes the specified policy via the console UI"""

        # Locate the policy in the list and open its details page
        policy_link = self.page.locator(f"//tr//a[@data-test-id='{name}']")
        policy_link.scroll_into_view_if_needed()
        policy_link.click()

        # Open the Actions dropdown menu
        actions_btn = self.page.locator("//button[contains(., 'Actions')]")
        actions_btn.wait_for(state="visible", timeout=10000)
        actions_btn.click()

        # Find and click the Delete action (supports PF v5 and v6)
        delete_button = self.page.locator(
            f"//button[@data-test-action='Delete {self.policy_type}'] | "  # PF v5
            f"//button[@role='menuitem' and contains(., 'Delete {self.policy_type}')] | "  # PF v6 (4.19)
            "//li[@data-test-action='Delete']"  # PF v6 (4.20) does not include policy type
        ).first
        delete_button.wait_for(state="visible", timeout=10000)
        delete_button.click()

        # Confirm the deletion in the confirmation dialog
        confirm_delete_btn = self.page.locator("//button[@data-test='confirm-action']")
        confirm_delete_btn.wait_for(state="visible", timeout=10000)
        confirm_delete_btn.click()

        # Wait for redirection back to the policy list view
        if self.policy_url_path not in self.page.url:
            self.page.wait_for_url(f"**/{self.policy_url_path}*", timeout=60000)

    def is_displayed(self):
        """Returns the create button locator"""
        return self.new_btn

    def page_displayed(self):
        """Check if the policy list page is displayed"""
        self.new_btn.wait_for(state="visible")
        return self.new_btn.is_visible()

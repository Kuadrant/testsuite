"""Page object for interacting with the Kuadrant / RHCL navigation menu in the OpenShift console"""

from testsuite.page_objects.navigator import step, Navigable
from testsuite.page_objects.policies.policies import PoliciesPage


class NavBar(Navigable):
    """Page object representing the OpenShift console navigation bar with Kuadrant / RHCL menu items"""

    def __init__(self, page):
        super().__init__(page)
        # Support for both upstream (Kuadrant) and downstream (Connectivity Link) nav labels
        self.kuadrant_nav = self.page.locator(
            "//button[contains(@class, 'nav__link') and (text() = 'Kuadrant' or text() = 'Connectivity Link')]"
        ).first

    def expand_kuadrant(self):
        """Expands the Kuadrant / RHCL navigation menu if it's currently collapsed"""
        self.kuadrant_nav.wait_for(state="visible", timeout=60000)
        if self.kuadrant_nav.get_attribute("aria-expanded") == "false":
            self.kuadrant_nav.click(timeout=60000)

    def overview(self):
        """Navigates to the console plugin Overview page"""
        self.expand_kuadrant()

    @step(PoliciesPage)
    def policies(self):
        """Navigates to the console plugin Policies page and returns a PoliciesPage object"""
        self.expand_kuadrant()
        self.page.locator("//a[contains(@class, 'nav__link') and text() = 'Policies']").click()

    def topology(self):
        """Navigates to the console plugin Topology page"""
        self.expand_kuadrant()

    def is_displayed(self):
        """Returns the nav button locator"""
        return self.kuadrant_nav

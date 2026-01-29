"""Page object for Policy details page from the overview page"""

from playwright.sync_api import Page

from testsuite.page_objects.overview.base_resources import BaseResourceNewPageYaml


class PolicyDetailsPage(BaseResourceNewPageYaml):
    """Page object for policy details page"""

    def __init__(self, page: Page, policy_type: str):
        super().__init__(page)
        self._policy_type = policy_type

    @property
    def resource_type(self) -> str:
        """Returns the policy type name"""
        return self._policy_type

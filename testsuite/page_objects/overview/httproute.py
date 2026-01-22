"""Page object for creating HTTPRoute on the overview page"""

import yaml
from playwright.sync_api import Page

from testsuite.page_objects.overview.base_resources import BaseResourceNewPageYaml


class HTTPRouteNewPageYaml(BaseResourceNewPageYaml):
    """Page object for creating a HTTPRoute using YAML editor"""

    @property
    def resource_type(self) -> str:
        """Returns the resource type name"""
        return "HTTPRoute"

    def __init__(self, page: Page):
        super().__init__(page)
        self.new_btn = page.get_by_text("Create HTTPRoute")

    def create(self, name: str, namespace: str = "kuadrant", gateway_name: str = "test-gateway") -> None:
        """Fill the YAML editor and create the HTTPRoute"""
        # Wait for the YAML editor to be visible
        self.editor.wait_for(state="visible")

        # Build HTTPRoute YAML
        httproute_yaml = {
            "apiVersion": "gateway.networking.k8s.io/v1",
            "kind": "HTTPRoute",
            "metadata": {"name": name, "namespace": namespace},
            "spec": {
                "parentRefs": [{"name": gateway_name, "namespace": namespace}],
                "rules": [{"matches": [{"path": {"type": "PathPrefix", "value": "/"}}]}],
            },
        }

        # Convert to YAML string
        yaml_text = yaml.safe_dump(httproute_yaml, sort_keys=False)

        # Inject YAML into Monaco editor
        self.page.evaluate(
            """(yaml) => {
                const editor = window.monaco?.editor?.getModels?.()?.[0];
                if (editor) editor.setValue(yaml);
            }""",
            yaml_text,
        )

        # Wait for Create button to be enabled
        self.page.wait_for_selector("#save-changes:not([disabled])")

        # Click Create
        self.create_btn.scroll_into_view_if_needed()
        self.create_btn.click()

        # Wait for the details page to load and display confirmation of creation
        self.page.wait_for_selector("text=HTTPRoute details", timeout=60000)

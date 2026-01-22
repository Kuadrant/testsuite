"""Page object for creating Gateway on the overview page"""

import yaml
from playwright.sync_api import Page

from testsuite.page_objects.overview.base_resources import BaseResourceNewPageYaml


class GatewayNewPageYaml(BaseResourceNewPageYaml):
    """Page object for creating a Gateway using YAML editor"""

    @property
    def resource_type(self) -> str:
        """Returns the resource type name"""
        return "Gateway"

    def __init__(self, page: Page):
        super().__init__(page)
        self.new_btn = page.get_by_text("Create Gateway")

    def create(self, name: str, namespace: str = "kuadrant", gateway_class: str = "istio") -> None:
        """Fill the YAML editor and create the gateway"""
        # Wait for the YAML editor to be visible
        self.editor.wait_for(state="visible")

        # Build gateway YAML
        gateway_yaml = {
            "apiVersion": "gateway.networking.k8s.io/v1",
            "kind": "Gateway",
            "metadata": {"name": name, "namespace": namespace},
            "spec": {
                "gatewayClassName": gateway_class,
                "listeners": [
                    {"name": "http", "port": 80, "protocol": "HTTP", "allowedRoutes": {"namespaces": {"from": "All"}}}
                ],
            },
        }

        # Convert to YAML string
        yaml_text = yaml.safe_dump(gateway_yaml, sort_keys=False)

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
        self.page.wait_for_selector("text=Gateway details", timeout=60000)

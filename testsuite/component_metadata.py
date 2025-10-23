"""Component metadata collection for Report Portal integration."""

import logging
from typing import Dict, Optional
from dataclasses import dataclass

import openshift_client as oc

from testsuite.config import settings
from testsuite.kubernetes.client import KubernetesClient


logger = logging.getLogger(__name__)


KUADRANT_COMPONENTS = {
    "kuadrant-operator": {
        "namespace": settings["service_protection"]["system_project"],
        "deployment": "kuadrant-operator-controller-manager",
        "container": "manager",
    },
    "authorino": {
        "namespace": settings["service_protection"]["system_project"],
        "deployment": "authorino",
        "container": "authorino",
    },
    "authorino-operator": {
        "namespace": settings["service_protection"]["system_project"],
        "deployment": "authorino-operator",
        "container": "manager",
    },
    "limitador": {
        "namespace": settings["service_protection"]["system_project"],
        "deployment": "limitador-limitador",
        "container": "limitador",
    },
    "limitador-operator": {
        "namespace": settings["service_protection"]["system_project"],
        "deployment": "limitador-operator-controller-manager",
        "container": "manager",
    },
    "dns-operator": {
        "namespace": settings["service_protection"]["system_project"],
        "deployment": "dns-operator-controller-manager",
        "container": "manager",
    },
    "console-plugin": {
        "namespace": settings["service_protection"]["system_project"],
        "deployment": "kuadrant-console-plugin",
        "container": "kuadrant-console-plugin",
    },
}


@dataclass
class ComponentImage:
    """Represents a component's image information."""

    name: str
    image: str
    tag: str
    digest: Optional[str] = None

    @property
    def image_with_digest(self) -> str:
        """Returns image with digest if available, otherwise with tag."""
        if self.digest:
            return f"{self.image.split(':')[0]}@{self.digest}"
        return f"{self.image}"


class ComponentMetadataCollector:
    """Collects component metadata for Report Portal integration."""

    def __init__(self, cluster: KubernetesClient):
        self.cluster = cluster

    def _get_deployment_pods(self, config: Dict[str, str]) -> list:
        """Get pods for a deployment based on its selector."""
        deployment = oc.selector(f"deployment/{config['deployment']}").object()

        if not deployment.exists():
            logger.warning("Deployment %s not found in %s", config["deployment"], config["namespace"])
            return []

        selector_labels = deployment.model.spec.selector.matchLabels
        labels_dict = dict(selector_labels)
        pods = oc.selector("pod", labels=labels_dict).objects()

        # Filter pods by deployment name for operators with generic selectors
        if config["deployment"] in [
            "limitador-operator-controller-manager",
            "kuadrant-operator-controller-manager",
        ]:
            deployment_name = config["deployment"].replace("-controller-manager", "")
            pods = [pod for pod in pods if deployment_name in pod.name()]

        return pods

    def _get_container_status(self, pod, container_name: str):
        """Get container status from pod."""
        container_statuses = pod.model.status.containerStatuses
        for status in container_statuses:
            if status.name == container_name:
                return status
        return None

    def _parse_image_info(self, container_status, component_name: str) -> ComponentImage:
        """Parse image information from container status."""
        image_id = container_status.imageID

        if "@sha256:" in image_id:
            image_name, digest = image_id.split("@", 1)
            tag = "unknown"
        else:
            image_name = container_status.image
            if ":" in image_name:
                image_name, tag = image_name.rsplit(":", 1)
            else:
                tag = "latest"
            digest = None

        return ComponentImage(name=component_name, image=image_name, tag=tag, digest=digest)

    def get_component_image(self, component_name: str) -> Optional[ComponentImage]:
        """Get image information for a specific component."""
        if component_name not in KUADRANT_COMPONENTS:
            logger.warning("Unknown component: %s", component_name)
            return None

        config = KUADRANT_COMPONENTS[component_name]

        try:
            namespace_client = self.cluster.change_project(config["namespace"])

            with namespace_client.context:
                pods = self._get_deployment_pods(config)
                if not pods:
                    logger.warning("No pods found for deployment %s", config["deployment"])
                    return None

                container_status = self._get_container_status(pods[0], config["container"])
                if not container_status:
                    logger.warning("Container %s status not found in pod", config["container"])
                    return None

                return self._parse_image_info(container_status, component_name)

        except (oc.OpenShiftPythonException, AttributeError, KeyError) as e:
            logger.error("Failed to get image for component %s: %s", component_name, e)
            return None

    def get_all_component_images(self) -> Dict[str, ComponentImage]:
        """Get image information for all known components."""
        components = {}

        for component_name in KUADRANT_COMPONENTS:
            image_info = self.get_component_image(component_name)
            if image_info:
                components[component_name] = image_info

        return components

    def get_component_metadata_for_report_portal(self) -> Dict[str, str]:
        """Get component metadata formatted for Report Portal attributes."""
        components = self.get_all_component_images()
        metadata = {}

        for component_name, image_info in components.items():
            # Only collect SHA digest - that's all we need to identify what's running
            if image_info.digest:
                # Remove 'sha256:' prefix for Report Portal compatibility (colons cause truncation)
                clean_digest = image_info.digest.replace("sha256:", "")
                metadata[f"{component_name}-sha"] = clean_digest
            else:
                # Fallback to tag if no digest available (shouldn't happen in normal deployments)
                metadata[f"{component_name}-tag"] = image_info.tag

        return metadata

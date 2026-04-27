"""Component metadata collection for Report Portal integration."""

import json
import logging
import re
from typing import Optional
from urllib.parse import urlparse

import openshift_client as oc

from testsuite.config import settings

logger = logging.getLogger(__name__)


class ReportPortalMetadataCollector:
    """Collects cluster metadata and formats it for ReportPortal integration."""

    def __init__(self):
        self.all_cluster_metadata = {}

    def collect_all_clusters(self):
        """Collect metadata from all configured clusters."""
        clusters_config = self._get_cluster_configurations()
        for cluster_name, cluster_client in clusters_config:
            metadata = self._collect_single_cluster(cluster_client)
            if metadata:
                self.all_cluster_metadata[cluster_name] = metadata

    def _get_cluster_configurations(self):
        """Get cluster configurations from settings."""
        clusters_config = [("cluster1", settings["control_plane"]["cluster"])]
        if cluster2 := settings["control_plane"].get("cluster2"):
            clusters_config.append(("cluster2", cluster2))
        if cluster3 := settings["control_plane"].get("cluster3"):
            clusters_config.append(("cluster3", cluster3))
        return clusters_config

    def _collect_single_cluster(self, cluster_client):
        """Collect metadata for a single cluster."""
        project = cluster_client.change_project(settings["service_protection"]["system_project"])
        if not project.connected:
            return None

        return {
            "metadata": self._get_kuadrant_metadata(project),
            "console_url": self._get_console_url(cluster_client.api_url),
            "ocp_version": self.get_ocp_version(project),
        }

    @staticmethod
    def _get_kuadrant_metadata(project) -> dict[str, str]:
        """Get kuadrant-operator image for Report Portal attributes."""
        metadata: dict[str, str] = {}
        deployment_name = "kuadrant-operator-controller-manager"
        container_name = "manager"
        try:
            with project.context:
                deployment = oc.selector(f"deployment/{deployment_name}").object()
                if not deployment.exists():
                    logger.warning("Deployment '%s' not found", deployment_name)
                    return metadata
                for container in deployment.model.spec.template.spec.containers:
                    if container.name == container_name:
                        metadata["kuadrant_image"] = container.image.split("@", 1)[0]
                        break
        except (oc.OpenShiftPythonException, AttributeError, KeyError, IndexError, ValueError) as e:
            logger.warning("Failed to get kuadrant-operator image: %s", e)
        return metadata

    @staticmethod
    def _get_console_url(api_url):
        """Generate console URL from API URL."""
        parsed = urlparse(api_url)
        hostname = parsed.hostname
        if hostname and hostname.startswith("api."):
            console_hostname = hostname.replace("api.", "console-openshift-console.apps.", 1)
            return f"https://{console_hostname}"
        return api_url

    @staticmethod
    def get_ocp_version(project) -> Optional[str]:
        """Retrieve and format OCP version from cluster."""
        try:
            with project.context:
                version_result = oc.selector("clusterversion").objects()
                if version_result:
                    ocp_version = version_result[0].model.status.history[0].version
                    if ocp_version:
                        parts = ocp_version.split(".")
                        if len(parts) >= 2:
                            return f"{parts[0]}.{parts[1]}"
        except (oc.OpenShiftPythonException, AttributeError, KeyError, IndexError, ValueError) as e:
            logger.warning("Failed to get OCP version: %s", e)

        return None

    @staticmethod
    def get_kubernetes_version(project) -> Optional[str]:
        """Run oc version and get the kubernetes version."""
        try:
            with project.context:
                version_result = oc.invoke("version", ["-o", "json"])
            version_data = json.loads(version_result.out())

            kubernetes_version = version_data.get("serverVersion", {}).get("gitVersion", None)
            if kubernetes_version:
                match = re.match(r"v([0-9]+\.[0-9]+)(\.[0-9]+)?", kubernetes_version)
                if match:
                    return match.groups()[0]
        except (oc.OpenShiftPythonException, AttributeError, KeyError, IndexError, ValueError) as e:
            logger.warning("Failed to get Kubernetes version: %s", e)
        return None

    @staticmethod
    def get_component_images(project) -> list[tuple]:
        """Get container images from pods in a namespace using openshift_client."""
        images = []
        try:
            with project.context:
                pods = oc.selector("pods").objects()

            seen = set()
            for pod in pods:
                for container in pod.model.spec.containers:
                    image = container.image
                    if not image:
                        continue
                    normalised_image = image.split("@", 1)[0]
                    if normalised_image in seen:
                        continue
                    seen.add(normalised_image)
                    print(f"{image=}")
                    image_name = normalised_image.split("/")[-1]
                    if ":" in image_name:
                        name, tag = image_name.rsplit(":", 1)
                        images.append((name, tag, image))
                    else:
                        logger.debug("Skipping image without tag: %s", image)
        except (oc.OpenShiftPythonException, AttributeError, KeyError, IndexError, ValueError) as e:
            logger.warning("Failed to get images from %s: %s", project, e)

        return images

    @staticmethod
    def get_istio_metadata(project) -> dict[str, str]:
        """Get Istio version and istiod image from the cluster."""
        metadata: dict[str, str] = {}
        try:
            with project.context:
                istio = oc.selector("istio").objects()
                if istio:
                    version = istio[0].model.spec.version
                    if version:
                        metadata["istio_version"] = version

                pods = oc.selector("pods", labels={"app": "istiod"}).objects()
                if pods:
                    image = pods[0].model.spec.containers[0].image
                    if image:
                        metadata["istiod_image"] = image
        except (oc.OpenShiftPythonException, AttributeError, KeyError, IndexError, ValueError) as e:
            logger.warning("Failed to get Istio metadata: %s", e)
        return metadata

    def get_cluster_metadata(self) -> dict:
        """Getter to collected cluster metadata information."""
        return self.all_cluster_metadata

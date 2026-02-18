"""Component metadata collection for Report Portal integration."""

import logging
from typing import Optional
from urllib.parse import urlparse

import openshift_client as oc

from testsuite.config import settings
from testsuite.kubernetes.client import KubernetesClient

logger = logging.getLogger(__name__)


class ComponentMetadataCollector:
    """Collects kuadrant-operator image metadata for Report Portal integration."""

    def __init__(self, cluster: KubernetesClient):
        self.cluster = cluster

    def get_kuadrant_operator_image(self) -> Optional[str]:
        """Get the kuadrant-operator image with tag (e.g., 'quay.io/kuadrant/kuadrant-operator:v1.0.0')."""
        namespace = settings["service_protection"]["system_project"]
        deployment_name = "kuadrant-operator-controller-manager"
        container_name = "manager"

        try:
            namespace_client = self.cluster.change_project(namespace)

            with namespace_client.context:
                deployment = oc.selector(f"deployment/{deployment_name}").object()

                if not deployment.exists():
                    logger.warning("Deployment %s not found in namespace %s", deployment_name, namespace)
                    return None

                selector_labels = deployment.model.spec.selector.matchLabels
                pods = oc.selector("pod", labels=dict(selector_labels)).objects()

                pods = [pod for pod in pods if "kuadrant-operator" in pod.name()]

                if not pods:
                    logger.warning("No pods found for deployment %s", deployment_name)
                    return None

                container_statuses = pods[0].model.status.containerStatuses
                container_status = None
                for status in container_statuses:
                    if status.name == container_name:
                        container_status = status
                        break

                if not container_status:
                    logger.warning("Container %s status not found in pod", container_name)
                    return None

                image_spec = container_status.image

                if "@" in image_spec:
                    image_spec = image_spec.split("@")[0]

                return image_spec

        except (oc.OpenShiftPythonException, AttributeError, KeyError) as e:
            logger.error("Failed to get kuadrant-operator image: %s", e)
            return None

    def get_component_metadata_for_report_portal(self) -> dict[str, str]:
        """Get kuadrant-operator image for Report Portal attributes."""
        metadata = {}

        kuadrant_image = self.get_kuadrant_operator_image()
        if kuadrant_image:
            metadata["kuadrant_image"] = kuadrant_image

        return metadata


class ReportPortalMetadataCollector:
    """Collects and manages cluster metadata for ReportPortal integration."""

    def __init__(self):
        self.all_cluster_metadata = {}

    def collect_all_clusters(self):
        """Collect metadata from all configured clusters."""
        clusters_config = self._get_cluster_configurations()
        for cluster_kubeconfig, cluster_client in clusters_config:
            metadata = self._collect_single_cluster(cluster_client)
            if metadata:
                self.all_cluster_metadata[cluster_kubeconfig] = metadata

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

        collector = ComponentMetadataCollector(project)
        component_metadata = collector.get_component_metadata_for_report_portal()
        console_url = self._get_console_url(cluster_client.api_url)
        ocp_version = self._get_ocp_version(project)

        return {
            "metadata": component_metadata,
            "console_url": console_url,
            "ocp_version": ocp_version,
        }

    def _get_console_url(self, api_url):
        """Generate console URL from API URL."""
        parsed = urlparse(api_url)
        hostname = parsed.hostname
        if hostname and hostname.startswith("api."):
            console_hostname = hostname.replace("api.", "console-openshift-console.apps.", 1)
            return f"https://{console_hostname}"
        return api_url

    def _get_ocp_version(self, project):
        """Retrieve and format OCP version from cluster."""
        with project.context:
            version_result = oc.selector("clusterversion").objects()
            if version_result:
                ocp_version = version_result[0].model.status.history[0].version
                if ocp_version:
                    parts = ocp_version.split(".")
                    if len(parts) >= 2:
                        return f"{parts[0]}.{parts[1]}"
        return None

    def add_properties_to_items(self, items):
        """Add cluster metadata as user properties to test items."""
        for cluster_kubeconfig in ["cluster1", "cluster2", "cluster3"]:
            if cluster_kubeconfig not in self.all_cluster_metadata:
                continue

            cluster_data = self.all_cluster_metadata[cluster_kubeconfig]
            if "kuadrant_image" not in cluster_data["metadata"]:
                continue

            property_value = self._build_property_value(cluster_data, cluster_kubeconfig)
            for item in items:
                item.user_properties.append((cluster_data["console_url"], property_value))

    def _build_property_value(self, cluster_data, cluster_kubeconfig):
        """Build property value string from cluster data."""
        property_value = f"Name:{cluster_kubeconfig}|"
        if cluster_data.get("ocp_version"):
            property_value += f"OCP:{cluster_data['ocp_version']}|"
        property_value += f"Kuadrant:{cluster_data['metadata']['kuadrant_image']}"
        return property_value

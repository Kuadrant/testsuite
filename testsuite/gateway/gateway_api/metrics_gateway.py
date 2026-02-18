"""Gateway-like wrapper around a LoadBalancer Service for metrics endpoint"""

from time import sleep
from typing import Optional

from testsuite.certificates import Certificate
from testsuite.config import settings
from testsuite.gateway import Gateway
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kubernetes.service import Service


class MetricsServiceGateway(Service, Gateway):
    """Gateway-like wrapper around a LoadBalancer Service for metrics endpoint

    Note: KuadrantGateway.commit() already creates a ClusterIP service named
    '{gateway.name()}-metrics' for internal metrics access. This class creates
    a separate LoadBalancer service for external access (needed on Kind/K8s).
    On OpenShift, use OpenshiftRoute to expose the ClusterIP service instead.
    """

    @property
    def cluster(self) -> KubernetesClient:
        """Returns KubernetesClient for this gateway"""
        return KubernetesClient.from_context(self.context)

    @property
    def service_name(self) -> str:
        """Service name for this gateway"""
        return self.model.metadata.name

    def external_ip(self) -> str:  # pylint: disable=invalid-overridden-method
        """Returns LoadBalancer IP and port to access this Gateway"""
        with self.context:
            return f"{self.refresh().model.status.loadBalancer.ingress[0].ip}:15020"

    def wait_for_ready(self, timeout: int = 90, slow_loadbalancers=False):
        """Waits until the LoadBalancer service gets an external IP"""
        super().wait_for_ready(timeout, slow_loadbalancers)
        if settings["control_plane"]["slow_loadbalancers"]:
            sleep(60)

    def get_tls_cert(self, hostname: str) -> Optional[Certificate]:
        """Metrics services don't use TLS, returns None"""
        return None

    @property
    def reference(self) -> dict[str, str]:
        """Returns dict for Gateway API style references"""
        return {
            "kind": "Service",
            "name": self.name(),
        }

    def delete(self, ignore_not_found=True, cmd_args=None):
        """Deletes the underlying service"""
        super().delete(ignore_not_found)

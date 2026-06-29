"""Module containing all the Backends"""

from abc import abstractmethod
from functools import cached_property
from typing import TYPE_CHECKING, Optional

from testsuite.gateway import Referencable, Exposable
from testsuite.lifecycle import LifecycleObject
from testsuite.kubernetes.client import KubernetesClient
from testsuite.utils.constants import HTTP_API_PORT

if TYPE_CHECKING:
    from testsuite.gateway import Hostname, Exposer


class Backend(LifecycleObject, Referencable, Exposable):
    """Backend (workload) deployed in Kubernetes"""

    def __init__(self, cluster: KubernetesClient, name: str, label: str):
        self._cluster = cluster

        self.name = name
        self.label = label

        self.deployment = None
        self.service = None
        self._admin_hostname: Optional["Hostname"] = None

    @property
    def cluster(self) -> KubernetesClient:
        """Returns KubernetesClient"""
        return self._cluster

    @property
    def reference(self):
        return {
            "group": "",
            "kind": "Service",
            "port": HTTP_API_PORT,
            "name": self.name,
            "namespace": self.cluster.project,
        }

    @property
    def service_name(self) -> str:
        return self.name

    @property
    def match_labels(self) -> dict[str, str]:
        """Pod selector labels used by this backend's deployment"""
        return {"app": self.label, "deployment": self.name}

    @property
    def admin_hostname(self) -> Optional["Hostname"]:
        """Returns Hostname for external admin access, or None if not exposed"""
        return self._admin_hostname

    def expose(self, exposer: "Exposer", name: str):
        """Creates external access for admin APIs via the exposer"""
        self._admin_hostname = exposer.expose_hostname(name, self)

    @property
    def url(self):
        """Returns internal URL for this backend"""
        return f"{self.name}.{self.cluster.project}.svc.cluster.local"

    @cached_property
    def port(self):
        """Service port that httpbin listens on"""
        return self.service.get_port("http").port

    @abstractmethod
    def commit(self):
        """Deploys the backend"""

    def delete(self):
        """Clean-up the backend"""
        with self.cluster.context:
            if self.service:
                self.service.delete()
                self.service = None
            if self.deployment:
                self.deployment.delete()
                self.deployment = None

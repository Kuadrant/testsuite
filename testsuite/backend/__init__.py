"""Module containing all the Backends"""

from abc import abstractmethod
from functools import cached_property

from testsuite.gateway import Referencable
from testsuite.lifecycle import LifecycleObject
from testsuite.kubernetes.client import KubernetesClient


class Backend(LifecycleObject, Referencable):
    """Backend (workload) deployed in Kubernetes"""

    def __init__(self, cluster: KubernetesClient, name: str, label: str):
        self.cluster = cluster
        self.name = name
        self.label = label

        self.deployment = None
        self.service = None

    @property
    def reference(self):
        return {"group": "", "kind": "Service", "port": 8080, "name": self.name, "namespace": self.cluster.project}

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

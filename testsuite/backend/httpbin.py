"""Httpbin implementation of Backend"""

from functools import cached_property

from testsuite.backend import Backend
from testsuite.kubernetes import Selector
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kubernetes.deployment import Deployment
from testsuite.kubernetes.service import Service, ServicePort


class Httpbin(Backend):
    """Httpbin deployed in Kubernetes as Backend"""

    def __init__(self, cluster: KubernetesClient, name, label, replicas=1) -> None:
        super().__init__()
        self.cluster = cluster
        self.name = name
        self.label = label
        self.replicas = replicas

        self.deployment = None
        self.service = None

    @property
    def reference(self):
        return {"group": "", "kind": "Service", "port": 8080, "name": self.name, "namespace": self.cluster.project}

    @property
    def url(self):
        """URL for the httpbin service"""
        return f"{self.name}.{self.cluster.project}.svc.cluster.local"

    def commit(self):
        match_labels = {"app": self.label, "deployment": self.name}
        self.deployment = Deployment.create_instance(
            self.cluster,
            self.name,
            container_name="httpbin",
            image="quay.io/jsmadis/httpbin:latest",
            ports={"api": 8080},
            selector=Selector(matchLabels=match_labels),
            labels={"app": self.label},
        )
        self.deployment.commit()
        self.deployment.wait_for_ready()

        self.service = Service.create_instance(
            self.cluster,
            self.name,
            selector=match_labels,
            ports=[ServicePort(name="http", port=8080, targetPort="api")],
        )
        self.service.commit()

    def delete(self):
        with self.cluster.context:
            if self.service:
                self.service.delete()
                self.service = None
            if self.deployment:
                self.deployment.delete()
                self.deployment = None

    @cached_property
    def port(self):
        """Service port that httpbin listens on"""
        return self.service.get_port("http").port

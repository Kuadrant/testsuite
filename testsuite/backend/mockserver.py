"""Mockserver implementation as Backend"""

from testsuite.backend import Backend
from testsuite.openshift import Selector
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.deployment import Deployment, ContainerResources
from testsuite.openshift.service import Service, ServicePort


class MockserverBackend(Backend):
    """Mockserver deployed as backend in Kubernetes"""

    PORT = 8080

    def __init__(self, openshift: OpenShiftClient, name: str, label: str):
        self.openshift = openshift
        self.name = name
        self.label = label

        self.deployment = None
        self.service = None

    @property
    def reference(self):
        return {
            "group": "",
            "kind": "Service",
            "port": self.PORT,
            "name": self.name,
            "namespace": self.openshift.project,
        }

    @property
    def url(self):
        return f"{self.name}.{self.openshift.project}.svc.cluster.local"

    def commit(self):
        match_labels = {"app": self.label, "deployment": self.name}
        self.deployment = Deployment.create_instance(
            self.openshift,
            self.name,
            container_name="mockserver",
            image="quay.io/mganisin/mockserver:latest",
            ports={"api": 1080},
            selector=Selector(matchLabels=match_labels),
            labels={"app": self.label},
            resources=ContainerResources(limits_memory="2G"),
            lifecycle={"postStart": {"exec": {"command": ["/bin/sh", "init-mockserver"]}}},
        )
        self.deployment.commit()
        self.deployment.wait_for_ready()

        self.service = Service.create_instance(
            self.openshift,
            self.name,
            selector=match_labels,
            ports=[ServicePort(name="1080-tcp", port=self.PORT, targetPort="api")],
            labels={"app": self.label},
        )
        self.service.commit()

    def delete(self):
        with self.openshift.context:
            if self.service:
                self.service.delete()
                self.service = None
            if self.deployment:
                self.deployment.delete()
                self.deployment = None

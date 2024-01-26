"""Httpbin related classes"""

from functools import cached_property

from testsuite.lifecycle import LifecycleObject
from testsuite.gateway import Referencable
from testsuite.openshift import Selector
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.deployment import Deployment
from testsuite.openshift.service import Service, ServicePort


class Httpbin(LifecycleObject, Referencable):
    """Httpbin deployed in OpenShift"""

    def __init__(self, openshift: OpenShiftClient, name, label, replicas=1) -> None:
        super().__init__()
        self.openshift = openshift
        self.name = name
        self.label = label
        self.replicas = replicas

        self.deployment = None
        self.service = None

    @property
    def reference(self):
        return {"group": "", "kind": "Service", "port": 8080, "name": self.name, "namespace": self.openshift.project}

    @property
    def url(self):
        """URL for the httpbin service"""
        return f"{self.name}.{self.openshift.project}.svc.cluster.local"

    def commit(self):
        match_labels = {"app": self.label, "deployment": self.name}
        self.deployment = Deployment.create_instance(
            self.openshift,
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
            self.openshift,
            self.name,
            selector=match_labels,
            ports=[ServicePort(name="http", port=8080, targetPort="api")],
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

    @cached_property
    def port(self):
        """Service port that httpbin listens on"""
        return self.service.get_port("http").port

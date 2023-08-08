"""Module for Httpbin backend classes"""
from functools import cached_property
from importlib import resources

from testsuite.objects import LifecycleObject
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects.gateway_api import Referencable


class Httpbin(LifecycleObject, Referencable):
    """Httpbin deployed in OpenShift through template"""

    def __init__(self, openshift: OpenShiftClient, name, label, replicas=1) -> None:
        super().__init__()
        self.openshift = openshift
        self.name = name
        self.label = label
        self.replicas = replicas

        self.httpbin_objects = None

    @property
    def reference(self):
        return {"group": "", "kind": "Service", "port": 8080, "name": self.name, "namespace": self.openshift.project}

    @property
    def url(self):
        """URL for the httpbin service"""
        return f"{self.name}.{self.openshift.project}.svc.cluster.local"

    def commit(self):
        self.httpbin_objects = self.openshift.new_app(
            resources.files("testsuite.resources").joinpath("httpbin.yaml"),
            {"NAME": self.name, "LABEL": self.label, "REPLICAS": self.replicas},
        )

        with self.openshift.context:
            assert self.openshift.is_ready(self.httpbin_objects.narrow("deployment")), "Httpbin wasn't ready in time"

    def delete(self):
        with self.openshift.context:
            if self.httpbin_objects:
                self.httpbin_objects.delete()
        self.httpbin_objects = None

    @cached_property
    def service(self):
        """Service associated with httpbin"""
        with self.openshift.context:
            return self.httpbin_objects.narrow("service").object()

    @cached_property
    def port(self):
        """Service port that httpbin listens on"""
        return self.service.model.spec.ports[0].get("port")

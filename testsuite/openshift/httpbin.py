"""Module for Httpbin backend classes"""
from functools import cached_property
from importlib import resources

from testsuite.objects import LifecycleObject
from testsuite.openshift.client import OpenShiftClient


class Httpbin(LifecycleObject):
    """Httpbin deployed in OpenShift through template"""

    def __init__(self, openshift: OpenShiftClient, name, label) -> None:
        super().__init__()
        self.openshift = openshift
        self.name = name
        self.label = label

        self.httpbin_objects = None

    @property
    def url(self):
        """URL for the httpbin service"""
        return f"{self.name}.{self.openshift.project}.svc.cluster.local"

    def commit(self):
        with resources.path("testsuite.resources", "httpbin.yaml") as path:
            self.httpbin_objects = self.openshift.new_app(path, {"NAME": self.name, "LABEL": self.label})

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

"""Httpbin backend combined with Envoy proxy"""
import time
from functools import cached_property
from importlib import resources

from httpx import Client


class EnvoyHttpbin:
    """Envoy + Httpbin deployed on OpenShift"""
    def __init__(self, openshift, authorino, name, label) -> None:
        self.openshift = openshift
        self.authorino = authorino
        self.name = name
        self.label = label

        self.envoy_objects = None
        self.httpbin_objects = None

    @cached_property
    def route(self):
        """Returns route for object"""
        with self.openshift.context:
            return self.envoy_objects.narrow("route").object()

    @cached_property
    def hostname(self):
        """Returns hostname of this envoy"""
        return self.route.model.spec.host

    @property
    def client(self):
        """Return Httpx client for the requests to this backend"""
        return Client(base_url=f"http://{self.hostname}")

    def create(self):
        """Deploy all required objects into OpenShift"""
        with resources.path("testsuite.resources", "httpbin.yaml") as path:
            self.httpbin_objects = self.openshift.new_app(path, {"NAME": self.name, "LABEL": self.label})

        with resources.path("testsuite.resources", "envoy.yaml") as path:
            self.envoy_objects = self.openshift.new_app(path, {
                "NAME": f"envoy-{self.name}",
                "LABEL": self.label,
                "AUTHORINO_URL": self.authorino.authorization_url,
                "UPSTREAM_URL": self.name
            })

        # TODO: better wait
        time.sleep(20)

    def destroy(self):
        """Destroy all objects this instance created"""
        with self.openshift.context:
            if self.envoy_objects:
                self.envoy_objects.delete()
            if self.httpbin_objects:
                self.httpbin_objects.delete()
        self.envoy_objects = None
        self.httpbin_objects = None

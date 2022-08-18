"""Httpbin backend combined with Envoy proxy"""
from functools import cached_property
from importlib import resources

from testsuite.httpx import HttpxBackoffClient
from testsuite.objects import LifecycleObject
from testsuite.openshift.client import OpenShiftClient


class Envoy(LifecycleObject):
    """Envoy deployed from template"""
    def __init__(self, openshift, authorino, name, label, httpbin_hostname) -> None:
        self.openshift = openshift
        self.authorino = authorino
        self.name = name
        self.label = label
        self.httpbin_hostname = httpbin_hostname

        self.envoy_objects = None

    @cached_property
    def route(self):
        """Returns route for object"""
        with self.openshift.context:
            return self.envoy_objects.narrow("route").object()

    def create_route(self, name):
        """Creates another route pointing to this Envoy"""
        service_name = f"envoy-{self.name}"
        route = self.openshift.do_action("expose", "service", f"--name={name}", "-o", "json",
                                         service_name, parse_output=True)
        with self.openshift.context:
            self.envoy_objects = self.envoy_objects.union(route.self_selector())
        return route

    @cached_property
    def hostname(self):
        """Returns hostname of this envoy"""
        return self.route.model.spec.host

    def client(self, **kwargs):
        """Return Httpx client for the requests to this backend"""
        return HttpxBackoffClient(base_url=f"http://{self.hostname}", **kwargs)

    def commit(self):
        """Deploy all required objects into OpenShift"""
        with resources.path("testsuite.resources", "envoy.yaml") as path:
            self.envoy_objects = self.openshift.new_app(path, {
                "NAME": f"envoy-{self.name}",
                "LABEL": self.label,
                "AUTHORINO_URL": self.authorino.authorization_url,
                "UPSTREAM_URL": self.httpbin_hostname
            })
        with self.openshift.context:
            assert self.openshift.is_ready(self.envoy_objects.narrow("deployment")), "Envoy wasn't ready in time"

    def delete(self):
        """Destroy all objects this instance created"""
        with self.openshift.context:
            if self.envoy_objects:
                self.envoy_objects.delete()
        self.envoy_objects = None


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


class TLSEnvoy(Envoy):
    """Envoy with TLS enabled and all required certificates set up, requires using a client certificate"""
    def __init__(self, openshift, authorino, name, label, httpbin_hostname,
                 authorino_ca_secret, envoy_ca_secret, envoy_cert_secret) -> None:
        super().__init__(openshift, authorino, name, label, httpbin_hostname)
        self.authorino_ca_secret = authorino_ca_secret
        self.backend_ca_secret = envoy_ca_secret
        self.envoy_cert_secret = envoy_cert_secret

    def client(self, **kwargs):
        """Return Httpx client for the requests to this backend"""
        return HttpxBackoffClient(base_url=f"https://{self.hostname}", **kwargs)

    def commit(self):
        with resources.path("testsuite.resources.tls", "envoy.yaml") as path:
            self.envoy_objects = self.openshift.new_app(path, {
                "NAME": f"envoy-{self.name}",
                "LABEL": self.label,
                "AUTHORINO_URL": self.authorino.authorization_url,
                "UPSTREAM_URL": self.httpbin_hostname,
                "AUTHORINO_CA_SECRET": self.authorino_ca_secret,
                "ENVOY_CA_SECRET": self.backend_ca_secret,
                "ENVOY_CERT_SECRET": self.envoy_cert_secret,
            })

        with self.openshift.context:
            assert self.openshift.is_ready(self.envoy_objects.narrow("deployment")), "Envoy wasn't ready in time"

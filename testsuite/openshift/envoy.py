"""Module containing all Envoy Classes"""
from functools import cached_property
from importlib import resources

from openshift import Selector

from testsuite.httpx import HttpxBackoffClient
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.httpbin import Httpbin
from testsuite.openshift.objects.proxy import Proxy
from testsuite.openshift.objects.route import OpenshiftRoute, Route


class Envoy(Proxy):
    """Envoy deployed from template"""
    def __init__(self, openshift: OpenShiftClient, authorino, name, label, httpbin: Httpbin, image) -> None:
        self.openshift = openshift
        self.authorino = authorino
        self.name = name
        self.label = label
        self.httpbin_hostname = httpbin.url
        self.image = image

        self.envoy_objects: Selector = None  # type: ignore

    @cached_property
    def route(self) -> Route:
        """Returns route for object"""
        with self.openshift.context:
            return self.envoy_objects\
                .narrow("route")\
                .narrow(lambda route: route.model.metadata.name == self.name)\
                .object(cls=OpenshiftRoute)

    def add_hostname(self, name) -> tuple[Route, str]:
        """Add another hostname that points to this Envoy"""
        route = OpenshiftRoute(dict_to_model=self.openshift.routes.expose(name, self.name).as_dict())
        with self.openshift.context:
            self.envoy_objects = self.envoy_objects.union(route.self_selector())
        return route, route.hostnames[0]

    @cached_property
    def hostname(self):
        """Returns hostname of this envoy"""
        return self.route.hostnames[0]

    def client(self, **kwargs):
        """Return Httpx client for the requests to this backend"""
        return HttpxBackoffClient(base_url=f"http://{self.hostname}", **kwargs)

    def commit(self):
        """Deploy all required objects into OpenShift"""
        with resources.path("testsuite.resources", "envoy.yaml") as path:
            self.envoy_objects = self.openshift.new_app(path, {
                "NAME": self.name,
                "LABEL": self.label,
                "AUTHORINO_URL": self.authorino.authorization_url,
                "UPSTREAM_URL": self.httpbin_hostname,
                "ENVOY_IMAGE": self.image
            })
        with self.openshift.context:
            assert self.openshift.is_ready(self.envoy_objects.narrow("deployment")), "Envoy wasn't ready in time"

    def delete(self):
        """Destroy all objects this instance created"""
        with self.openshift.context:
            if self.envoy_objects:
                self.envoy_objects.delete()
        self.envoy_objects = None


class TLSEnvoy(Envoy):
    """Envoy with TLS enabled and all required certificates set up, requires using a client certificate"""
    def __init__(self, openshift, authorino, name, label, httpbin_hostname, image,
                 authorino_ca_secret, envoy_ca_secret, envoy_cert_secret) -> None:
        super().__init__(openshift, authorino, name, label, httpbin_hostname, image)
        self.authorino_ca_secret = authorino_ca_secret
        self.backend_ca_secret = envoy_ca_secret
        self.envoy_cert_secret = envoy_cert_secret

    def client(self, **kwargs):
        """Return Httpx client for the requests to this backend"""
        return HttpxBackoffClient(base_url=f"https://{self.hostname}", **kwargs)

    def commit(self):
        with resources.path("testsuite.resources.tls", "envoy.yaml") as path:
            self.envoy_objects = self.openshift.new_app(path, {
                "NAME": self.name,
                "LABEL": self.label,
                "AUTHORINO_URL": self.authorino.authorization_url,
                "UPSTREAM_URL": self.httpbin_hostname,
                "AUTHORINO_CA_SECRET": self.authorino_ca_secret,
                "ENVOY_CA_SECRET": self.backend_ca_secret,
                "ENVOY_CERT_SECRET": self.envoy_cert_secret,
                "ENVOY_IMAGE": self.image
            })

        with self.openshift.context:
            assert self.openshift.is_ready(self.envoy_objects.narrow("deployment")), "Envoy wasn't ready in time"

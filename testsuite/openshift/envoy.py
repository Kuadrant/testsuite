"""Module containing all Envoy Classes"""
from importlib import resources

from openshift import Selector

from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.httpbin import Httpbin
from testsuite.openshift.objects.proxy import Proxy
from testsuite.openshift.objects.route import OpenshiftRoute


# pylint: disable=too-many-instance-attributes
class Envoy(Proxy):
    """Envoy deployed from template"""

    def __init__(
        self, openshift: OpenShiftClient, authorino, name, label, httpbin: Httpbin, image, template=None
    ) -> None:
        self.openshift = openshift
        self.authorino = authorino
        self.name = name
        self.label = label
        self.httpbin_hostname = httpbin.url
        self.image = image
        self.template = template or resources.files("testsuite.resources").joinpath("envoy.yaml")

        self.envoy_objects: Selector = None  # type: ignore

    def expose_hostname(self, name) -> OpenshiftRoute:
        """Add another hostname that points to this Envoy"""
        route = OpenshiftRoute.create_instance(
            self.openshift, name, service_name=self.name, target_port="web", labels={"app": self.label}
        )
        route.commit()
        with self.openshift.context:
            self.envoy_objects = self.envoy_objects.union(route.self_selector())
        return route

    def commit(self):
        """Deploy all required objects into OpenShift"""
        self.envoy_objects = self.openshift.new_app(
            self.template,
            {
                "NAME": self.name,
                "LABEL": self.label,
                "AUTHORINO_URL": self.authorino.authorization_url,
                "UPSTREAM_URL": self.httpbin_hostname,
                "ENVOY_IMAGE": self.image,
            },
        )
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

    def __init__(
        self,
        openshift,
        authorino,
        name,
        label,
        httpbin_hostname,
        image,
        authorino_ca_secret,
        envoy_ca_secret,
        envoy_cert_secret,
    ) -> None:
        super().__init__(openshift, authorino, name, label, httpbin_hostname, image)
        self.authorino_ca_secret = authorino_ca_secret
        self.backend_ca_secret = envoy_ca_secret
        self.envoy_cert_secret = envoy_cert_secret

    def expose_hostname(self, name) -> OpenshiftRoute:
        """Add another hostname that points to this Envoy"""
        route = OpenshiftRoute.create_instance(
            self.openshift,
            name,
            service_name=self.name,
            target_port="web",
            labels={"app": self.label},
            tls=True,
            termination="passthrough",
        )
        route.commit()
        with self.openshift.context:
            self.envoy_objects = self.envoy_objects.union(route.self_selector())
        return route

    def commit(self):
        self.envoy_objects = self.openshift.new_app(
            resources.files("testsuite.resources.tls").joinpath("envoy.yaml"),
            {
                "NAME": self.name,
                "LABEL": self.label,
                "AUTHORINO_URL": self.authorino.authorization_url,
                "UPSTREAM_URL": self.httpbin_hostname,
                "AUTHORINO_CA_SECRET": self.authorino_ca_secret,
                "ENVOY_CA_SECRET": self.backend_ca_secret,
                "ENVOY_CERT_SECRET": self.envoy_cert_secret,
                "ENVOY_IMAGE": self.image,
            },
        )

        with self.openshift.context:
            assert self.openshift.is_ready(self.envoy_objects.narrow("deployment")), "Envoy wasn't ready in time"

"""Module containing all route classes"""

import typing

from functools import cached_property

from httpx import Client

from testsuite.httpx import KuadrantClient
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects import modify, OpenShiftObject
from testsuite.openshift.objects.route import Route

from . import Referencable


if typing.TYPE_CHECKING:
    from testsuite.openshift.httpbin import Httpbin


class HTTPRoute(OpenShiftObject, Referencable):
    """HTTPRoute object, serves as replacement for Routes and Ingresses"""

    def client(self, **kwargs) -> Client:
        """Returns HTTPX client"""
        return KuadrantClient(base_url=f"http://{self.hostnames[0]}", **kwargs)

    @classmethod
    def create_instance(
        cls,
        openshift: OpenShiftClient,
        name,
        parent: Referencable,
        hostname,
        backend: "Httpbin",
        labels: dict[str, str] = None,
    ):
        """Creates new instance of HTTPRoute"""
        model = {
            "apiVersion": "gateway.networking.k8s.io/v1beta1",
            "kind": "HTTPRoute",
            "metadata": {"name": name, "namespace": openshift.project, "labels": labels},
            "spec": {
                "parentRefs": [parent.reference],
                "hostnames": [hostname],
                "rules": [{"backendRefs": [backend.reference]}],
            },
        }

        return cls(model, context=openshift.context)

    @property
    def reference(self):
        return {
            "group": "gateway.networking.k8s.io",
            "kind": "HTTPRoute",
            "name": self.name(),
            "namespace": self.namespace(),
        }

    @property
    def hostnames(self):
        """Return all hostnames for this HTTPRoute"""
        return self.model.spec.hostnames

    @modify
    def add_hostname(self, hostname):
        """Adds hostname to the Route"""
        if hostname not in self.model.spec.hostnames:
            self.model.spec.hostnames.append(hostname)

    @modify
    def remove_hostname(self, hostname):
        """Adds hostname to the Route"""
        self.model.spec.hostnames.remove(hostname)

    @modify
    def remove_all_hostnames(self):
        """Adds hostname to the Route"""
        self.model.spec.hostnames = []

    @modify
    def set_match(self, path_prefix: str = None, headers: dict[str, str] = None):
        """Limits HTTPRoute to a certain path"""
        match = {}
        if path_prefix:
            match["path"] = {"value": path_prefix, "type": "PathPrefix"}
        if headers:
            match["headers"] = headers
        self.model.spec.rules[0]["matches"] = [match]


class HostnameWrapper(Route, Referencable):
    """
    Wraps HTTPRoute with Route interface with specific hostname defined for a client
    Needed because there can be only HTTPRoute for Kuadrant, while there will be multiple OpenshiftRoutes for AuthConfig
    """

    def __init__(self, route: HTTPRoute, hostname: str) -> None:
        super().__init__()
        self.route = route
        self._hostname = hostname

    @cached_property
    def hostname(self) -> str:
        return self._hostname

    def client(self, **kwargs) -> Client:
        return KuadrantClient(base_url=f"http://{self.hostname}", **kwargs)

    @property
    def reference(self) -> dict[str, str]:
        return self.route.reference

    def __getattr__(self, attr):
        """Direct all other calls to the original route"""
        return getattr(self.route, attr)

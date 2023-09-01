"""Module containing all Gateway API related classes"""
import typing
from abc import ABC, abstractmethod
from functools import cached_property

import openshift
from openshift import Selector, ModelError

from testsuite.httpx import HttpxBackoffClient
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects import OpenShiftObject, modify
from testsuite.openshift.objects.proxy import Proxy
from testsuite.openshift.objects.route import Route
from testsuite.utils import randomize

if typing.TYPE_CHECKING:
    from testsuite.openshift.httpbin import Httpbin


class Referencable(ABC):
    """Object that can be referenced in Gateway API style"""

    @property
    @abstractmethod
    def reference(self) -> dict[str, str]:
        """
        Returns dict, which can be used as reference in Gateway API Objects.
        https://gateway-api.sigs.k8s.io/references/spec/#gateway.networking.k8s.io/v1beta1.ParentReference
        """


class HTTPRoute(OpenShiftObject, Referencable, Route):
    """HTTPRoute object, serves as replacement for Routes and Ingresses"""

    @cached_property
    def hostnames(self):
        return self.model.spec.hostnames

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
            "apiVersion": "gateway.networking.k8s.io/v1alpha2",
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


# pylint: disable=too-many-instance-attributes
class Gateway(Referencable, Proxy):
    """Gateway object already present on the server"""

    def __init__(self, openshift: OpenShiftClient, name, namespace, label, httpbin: "Httpbin") -> None:
        super().__init__()
        self.openshift = openshift
        self.system_openshift = openshift.change_project(namespace)
        self.name = name
        self.label = label
        self.namespace = namespace
        self.httpbin = httpbin

        self._route: HTTPRoute = None  # type: ignore
        self._selector: Selector = None  # type: ignore

    def _expose_route(self, name, service):
        return self.system_openshift.routes.expose(name, service, port=8080)

    @cached_property
    def route(self) -> HTTPRoute:
        return self._route

    def add_hostname(self, name) -> str:
        route = self._expose_route(name, self.name)
        self._selector = self._selector.union(route.self_selector())
        self.route.add_hostname(route.model.spec.host)
        return route.model.spec.host

    def client(self, **kwargs):
        """Return Httpx client for the requests to this backend"""
        return HttpxBackoffClient(base_url=f"http://{self.route.hostnames[0]}", **kwargs)

    def commit(self):
        name = randomize(self.name)
        route = self._expose_route(name, self.name)
        self._selector = route.self_selector()

        self._route = HTTPRoute.create_instance(
            self.openshift, name, self, route.model.spec.host, self.httpbin, {"app": self.label}
        )
        self._route.commit()

    def delete(self):
        with self.openshift.context:
            self._route.delete()
            self._selector.delete()

    @property
    def reference(self):
        return {"group": "gateway.networking.k8s.io", "kind": "Gateway", "name": self.name, "namespace": self.namespace}


class MGCGateway(OpenShiftObject, Referencable):
    """Gateway object for purposes of MGC"""

    @classmethod
    def create_instance(
        cls,
        openshift: OpenShiftClient,
        name: str,
        gateway_class_name: str,
        hostname: str,
        placement: typing.Optional[str] = None,
    ):
        """Creates new instance of Gateway"""
        labels = {}
        if placement is not None:
            labels = {"cluster.open-cluster-management.io/placement": placement}

        model = {
            "apiVersion": "gateway.networking.k8s.io/v1beta1",
            "kind": "Gateway",
            "metadata": {"name": name, "namespace": openshift.project, "labels": labels},
            "spec": {
                "gatewayClassName": gateway_class_name,
                "listeners": [
                    {
                        "name": "api",
                        "port": 443,
                        "protocol": "HTTPS",
                        "hostname": hostname,
                        "allowedRoutes": {"namespaces": {"from": "All"}},
                    }
                ],
            },
        }

        return cls(model, context=openshift.context)

    def is_ready(self):
        """Checks whether the gateway got its IP address assigned thus is ready"""
        try:
            addresses = self.model["status"]["addresses"]
            multi_cluster_addresses = [
                address for address in addresses if address["type"] == "kuadrant.io/MultiClusterIPAddress"
            ]
            return len(multi_cluster_addresses) > 0
        except (KeyError, ModelError):
            return False

    def wait_for_ready(self):
        """Waits for the gateway to be ready in the sense of is_ready(self)"""
        with openshift.timeout(90):
            success, _, _ = self.self_selector().until_all(success_func=lambda obj: MGCGateway(obj.model).is_ready())
            assert success, "Gateway didn't get ready in time"
            self.refresh()

    @property
    def hostname(self):
        """Hostname of the first listener"""
        return self.model["spec"]["listeners"][0]["hostname"]

    @property
    def reference(self):
        return {
            "group": "gateway.networking.k8s.io",
            "kind": "Gateway",
            "name": self.name(),
            "namespace": self.namespace(),
        }

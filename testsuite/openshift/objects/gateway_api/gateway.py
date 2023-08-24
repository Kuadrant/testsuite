"""Module containing all gateway classes"""
import typing

import openshift
from openshift import Selector, ModelError

from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects import OpenShiftObject
from testsuite.openshift.objects.proxy import Proxy
from testsuite.openshift.objects.route import Route
from . import Referencable
from .route import HTTPRoute, HostnameWrapper

if typing.TYPE_CHECKING:
    from testsuite.openshift.httpbin import Httpbin


class Gateway(OpenShiftObject, Referencable):
    """Gateway object for purposes of MGC"""

    @classmethod
    def create_instance(
        cls,
        openshift: OpenShiftClient,
        name: str,
        gateway_class: str,
        hostname: str,
        labels: dict[str, str] = None,
    ):
        """Creates new instance of Gateway"""

        model = {
            "apiVersion": "gateway.networking.k8s.io/v1beta1",
            "kind": "Gateway",
            "metadata": {"name": name, "labels": labels},
            "spec": {
                "gatewayClassName": gateway_class,
                "listeners": [
                    {
                        "name": "api",
                        "port": 8080,
                        "protocol": "HTTP",
                        "hostname": hostname,
                        "allowedRoutes": {"namespaces": {"from": "All"}},
                    }
                ],
            },
        }

        return cls(model, context=openshift.context)

    def wait_for_ready(self) -> bool:
        """Waits for the gateway to be ready"""
        return True

    @property
    def hostname(self):
        """Hostname of the first listener"""
        return self.model.spec.listeners[0].hostname

    @property
    def reference(self):
        return {
            "group": "gateway.networking.k8s.io",
            "kind": "Gateway",
            "name": self.name(),
            "namespace": self.namespace(),
        }


class MGCGateway(Gateway):
    """Gateway object for purposes of MGC"""

    @classmethod
    def create_instance(
        cls,
        openshift: OpenShiftClient,
        name: str,
        gateway_class: str,
        hostname: str,
        labels: dict[str, str] = None,
        placement: typing.Optional[str] = None,
    ):
        """Creates new instance of Gateway"""
        if labels is None:
            labels = {}

        if placement is not None:
            labels["cluster.open-cluster-management.io/placement"] = placement

        return Gateway.create_instance(openshift, name, gateway_class, hostname, labels)

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


class GatewayProxy(Proxy):
    """Wrapper for Gateway object to make it a Proxy implementation e.g. exposing hostnames outside of the cluster"""

    def __init__(self, openshift: OpenShiftClient, gateway: Gateway, label, backend: "Httpbin") -> None:
        super().__init__()
        self.openshift = openshift
        self.gateway = gateway
        self.name = gateway.name()
        self.label = label
        self.backend = backend

        self.route: HTTPRoute = None  # type: ignore
        self.selector: Selector = None  # type: ignore

    def _expose_route(self, name, service):
        return self.openshift.routes.expose(name, service, port="api")

    def expose_hostname(self, name) -> Route:
        route = self._expose_route(name, self.name)
        if self.route is None:
            self.route = HTTPRoute.create_instance(
                self.openshift,
                self.name,
                self.gateway,
                route.model.spec.host,
                self.backend,
                labels={"app": self.label},
            )
            self.selector = self.route.self_selector()
            self.route.commit()
        else:
            self.route.add_hostname(route.model.spec.host)
        self.selector.union(route.self_selector())
        return HostnameWrapper(self.route, route.model.spec.host)

    def commit(self):
        pass

    def delete(self):
        self.selector.delete()

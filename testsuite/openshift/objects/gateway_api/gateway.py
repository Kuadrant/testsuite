"""Module containing all gateway classes"""
import typing

import openshift
from openshift import Selector, ModelError

from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects import OpenShiftObject
from testsuite.openshift.objects.proxy import Proxy
from testsuite.openshift.objects.route import Route
from testsuite.utils import randomize

from . import Referencable
from .route import HTTPRoute, HostnameWrapper

if typing.TYPE_CHECKING:
    from testsuite.openshift.httpbin import Httpbin


# pylint: disable=too-many-instance-attributes
class Gateway(Referencable, Proxy):
    """Gateway object already present on the server"""

    def __init__(self, openshift: OpenShiftClient, name, namespace, label, backend: "Httpbin") -> None:
        super().__init__()
        self.openshift = openshift
        self.system_openshift = openshift.change_project(namespace)
        self.name = name
        self.label = label
        self.namespace = namespace
        self.backend = backend

        self.route: HTTPRoute = None  # type: ignore
        self.selector: Selector = None  # type: ignore

    def _expose_route(self, name, service):
        return self.system_openshift.routes.expose(name, service, port=8080)

    def expose_hostname(self, name) -> Route:
        route = self._expose_route(name, self.name)
        if self.route is None:
            self.route = HTTPRoute.create_instance(
                self.openshift,
                randomize(self.name),
                self,
                route.model.spec.host,
                self.backend,
                labels={"app": self.label},
            )
            self.selector = self.route.self_selector()
            self.route.commit()
        else:
            self.route.add_hostname(route.model.spec.host)
        self.selector = self.selector.union(route.self_selector())
        return HostnameWrapper(self.route, route.model.spec.host)

    def commit(self):
        pass

    def delete(self):
        with self.openshift.context:
            self.selector.delete()

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

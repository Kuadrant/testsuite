"""Module containing all gateway classes"""
import json
import typing

from openshift import Selector, timeout, selector

from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects import OpenShiftObject
from testsuite.openshift.objects.proxy import Proxy
from testsuite.openshift.objects.route import Route, OpenshiftRoute
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
        kuadrant_namespace: str,
        labels: dict[str, str] = None,
    ):
        """Creates new instance of Gateway"""

        model = {
            "apiVersion": "gateway.networking.k8s.io/v1beta1",
            "kind": "Gateway",
            "metadata": {
                "name": name,
                "labels": labels,
                "annotations": {"kuadrant.io/namespace": kuadrant_namespace},
            },
            "spec": {
                "gatewayClassName": gateway_class,
                "listeners": [
                    {
                        "name": "api",
                        "port": 80,
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
    def openshift(self):
        """Hostname of the first listener"""
        return OpenShiftClient.from_context(self.context)

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
        kuadrant_namespace: str,
        labels: dict[str, str] = None,
        placement: typing.Optional[str] = None,
    ):
        """Creates new instance of Gateway"""
        if labels is None:
            labels = {}

        if placement is not None:
            labels["cluster.open-cluster-management.io/placement"] = placement

        return super(MGCGateway, cls).create_instance(
            openshift, name, gateway_class, hostname, kuadrant_namespace, labels
        )

    def get_spoke_gateway(self, spokes: dict[str, OpenShiftClient]) -> "MGCGateway":
        """
        Returns spoke gateway on an arbitrary, and sometimes, random spoke cluster.
        Works only for GW deployed on Hub
        """
        self.refresh()
        cluster_name = json.loads(self.model.metadata.annotations["kuadrant.io/gateway-clusters"])[0]
        spoke_client = spokes[cluster_name]
        prefix = "kuadrant"
        spoke_client = spoke_client.change_project(f"{prefix}-{self.namespace()}")
        with spoke_client.context:
            return selector(f"gateway/{self.name()}").object(cls=self.__class__)

    def is_ready(self):
        """Check the programmed status"""
        for condition in self.model.status.conditions:
            if condition.type == "Programmed" and condition.status == "True":
                return True
        return False

    def wait_for_ready(self):
        """Waits for the gateway to be ready in the sense of is_ready(self)"""
        with timeout(600):
            success, _, _ = self.self_selector().until_all(
                success_func=lambda obj: self.__class__(obj.model).is_ready()
            )
            assert success, "Gateway didn't get ready in time"
            self.refresh()
            return success

    def delete(self, ignore_not_found=True, cmd_args=None):
        with timeout(90):
            super().delete(ignore_not_found, cmd_args)


class GatewayProxy(Proxy):
    """Wrapper for Gateway object to make it a Proxy implementation e.g. exposing hostnames outside of the cluster"""

    def __init__(self, gateway: Gateway, label, backend: "Httpbin") -> None:
        super().__init__()
        self.openshift = gateway.openshift
        self.gateway = gateway
        self.name = gateway.name()
        self.label = label
        self.backend = backend

        self.route: HTTPRoute = None  # type: ignore
        self.selector: Selector = None  # type: ignore

    def expose_hostname(self, name) -> Route:
        route = OpenshiftRoute.create_instance(self.openshift, name, self.name, "api")
        route.commit()
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
        if self.selector:
            self.selector.delete()
            self.selector = None

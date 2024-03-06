"""Module containing Route related stuff"""

from functools import cached_property

from httpx import Client

from testsuite.httpx import KuadrantClient
from testsuite.gateway import Hostname
from testsuite.openshift import OpenShiftObject


class OpenshiftRoute(OpenShiftObject, Hostname):
    """Openshift Route object"""

    @classmethod
    def create_instance(
        cls,
        openshift,
        name,
        service_name,
        target_port: int | str,
        tls=False,
        termination="edge",
        labels: dict[str, str] = None,
    ):
        """Creates new OpenshiftRoute instance"""
        model = {
            "apiVersion": "route.openshift.io/v1",
            "kind": "Route",
            "metadata": {"name": name, "labels": labels},
            "spec": {
                "to": {"name": service_name, "kind": "Service"},
                "port": {"targetPort": target_port},
            },
        }
        if tls:
            model["spec"]["tls"] = {"termination": termination}  # type: ignore
        return cls(model, context=openshift.context)

    def client(self, **kwargs) -> Client:
        protocol = "http"
        if "tls" in self.model.spec:
            protocol = "https"
        return KuadrantClient(base_url=f"{protocol}://{self.hostname}", **kwargs)

    @cached_property
    def hostname(self):
        return self.model.spec.host

"""Module containing Route related stuff"""

from functools import cached_property

from testsuite.httpx import KuadrantClient
from testsuite.gateway import Hostname
from testsuite.kubernetes import KubernetesObject


class OpenshiftRoute(KubernetesObject, Hostname):
    """Openshift Route object"""

    def __init__(self, dict_to_model=None, string_to_model=None, context=None):
        super().__init__(dict_to_model, string_to_model, context)
        self.verify = None

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

    def client(self, **kwargs) -> KuadrantClient:
        protocol = "http"
        if "tls" in self.model.spec:
            protocol = "https"
            kwargs.setdefault("verify", self.verify)
        return KuadrantClient(base_url=f"{protocol}://{self.hostname}", **kwargs)

    @cached_property
    def hostname(self):
        return self.model.spec.host

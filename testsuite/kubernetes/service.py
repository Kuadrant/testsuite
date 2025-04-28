"""Service related objects"""

from time import sleep
from dataclasses import dataclass, asdict
from typing import Literal

from openshift_client import timeout, Missing

from testsuite.kubernetes import KubernetesObject


@dataclass
class ServicePort:
    """Kubernetes Service Port object"""

    name: str
    port: int
    targetPort: int | str  # pylint: disable=invalid-name


class Service(KubernetesObject):
    """Kubernetes Service object"""

    @classmethod
    def create_instance(
        cls,
        cluster,
        name,
        selector: dict[str, str],
        ports: list[ServicePort],
        labels: dict[str, str] = None,
        service_type: Literal["ClusterIP", "LoadBalancer", "NodePort", "ExternalName"] = None,
    ):
        """Creates new Service"""
        model: dict = {
            "kind": "Service",
            "apiVersion": "v1",
            "metadata": {
                "name": name,
                "labels": labels,
            },
            "spec": {"ports": [asdict(port) for port in ports], "selector": selector},
        }

        if service_type is not None:
            model["spec"]["type"] = service_type

        return cls(model, context=cluster.context)

    def get_port(self, name):
        """Returns port definition for a port with said name"""
        for port in self.model.spec.ports:
            if port["name"] == name:
                return port
        raise KeyError(f"No port with name {name} exists")

    @property
    def external_ip(self):
        """Returns LoadBalancer IP for this service"""
        if self.model.spec.type != "LoadBalancer":
            raise AttributeError("External IP can be only used with LoadBalancer services")
        ip = self.model.status.loadBalancer.ingress[0].ip

        # If static IP is not used then hostname might be used instead
        if ip is Missing:
            ip = self.model.status.loadBalancer.ingress[0].hostname
        if ip is Missing:
            raise AttributeError(f"Neither External IP nor Hostname found in status of {self.kind()}/{self.name()}")

        return ip

    def delete(self, ignore_not_found=True, cmd_args=None):
        """Deletes Service, introduces bigger waiting times due to LoadBalancer type"""
        with timeout(10 * 60):
            deleted = super(KubernetesObject, self).delete(ignore_not_found, cmd_args)
            return deleted

    def wait_for_ready(self, timeout=60 * 5, slow_loadbalancers=False):
        """Waits until LoadBalancer service gets ready."""
        if self.model.spec.type != "LoadBalancer":
            return
        success = self.wait_until(
            lambda obj: "ip" in self.refresh().model.status.loadBalancer.ingress[0]
            or "hostname" in self.refresh().model.status.loadBalancer.ingress[0],
            timelimit=timeout,
        )
        assert success, f"Service {self.name()} did not get ready in time"
        if slow_loadbalancers:
            sleep(60)

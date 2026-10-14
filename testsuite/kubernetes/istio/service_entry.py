"""Istio ServiceEntry related objects"""

from testsuite.kubernetes import KubernetesObject
from testsuite.kubernetes.client import KubernetesClient


class ServiceEntry(KubernetesObject):
    """Istio ServiceEntry object for registering external services in the mesh"""

    @classmethod
    def create_instance(
        cls,
        cluster: KubernetesClient,
        name: str,
        hosts: list[str],
        ports: list[dict],
        location: str = "MESH_EXTERNAL",
        resolution: str = "DNS",
        endpoints: list[dict] = None,
        labels: dict[str, str] = None,
    ):
        """Creates new instance of ServiceEntry.

        Pass `endpoints` together with `resolution="STATIC"` to register a host that has no
        DNS record, e.g. a LoadBalancer IP on Kind.
        """
        model: dict = {
            "apiVersion": "networking.istio.io/v1",
            "kind": "ServiceEntry",
            "metadata": {
                "name": name,
                "namespace": cluster.project,
                "labels": labels,
            },
            "spec": {
                "hosts": hosts,
                "ports": ports,
                "location": location,
                "resolution": resolution,
            },
        }
        if endpoints:
            model["spec"]["endpoints"] = endpoints
        return cls(model, context=cluster.context)

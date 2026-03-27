"""Istio DestinationRule related objects"""

from testsuite.kubernetes import KubernetesObject
from testsuite.kubernetes.client import KubernetesClient


class DestinationRule(KubernetesObject):
    """Istio DestinationRule object for configuring traffic policy to a destination"""

    @classmethod
    def create_instance(
        cls,
        cluster: KubernetesClient,
        name: str,
        host: str,
        tls_mode: str = None,
        sni: str = None,
        credential_name: str = None,
        labels: dict[str, str] = None,
    ):
        """Creates new instance of DestinationRule"""
        model: dict = {
            "apiVersion": "networking.istio.io/v1",
            "kind": "DestinationRule",
            "metadata": {
                "name": name,
                "namespace": cluster.project,
                "labels": labels,
            },
            "spec": {"host": host},
        }

        if tls_mode:
            model["spec"].setdefault("trafficPolicy", {}).setdefault("tls", {})["mode"] = tls_mode
        if sni:
            model["spec"].setdefault("trafficPolicy", {}).setdefault("tls", {})["sni"] = sni
        if credential_name:
            model["spec"].setdefault("trafficPolicy", {}).setdefault("tls", {})["credentialName"] = credential_name

        return cls(model, context=cluster.context)

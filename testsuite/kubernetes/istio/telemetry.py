"""Istio Telemetry related objects"""

from testsuite.kubernetes import KubernetesObject
from testsuite.kubernetes.client import KubernetesClient

TELEMETRY_CRD = "telemetries.telemetry.istio.io"


class Telemetry(KubernetesObject):
    """Istio Telemetry object for scoping tracing and access logging to selected workloads"""

    @classmethod
    def create_instance(
        cls,
        cluster: KubernetesClient,
        name: str,
        tracing: list[dict],
        gateway_name: str = None,
        selector: dict[str, str] = None,
        labels: dict[str, str] = None,
    ):
        """Creates new instance of Telemetry.

        Scope it with either `gateway_name`, which targets the Gateway through `targetRefs` as
        Istio documents for gateways, or `selector` pod labels. Leaving both unset makes the
        resource namespace-wide, which would change tracing behaviour for every proxy in the
        namespace, so one of them is required.
        """
        if (gateway_name is None) == (selector is None):
            raise ValueError("Telemetry needs exactly one of gateway_name or selector to scope it")

        model: dict = {
            "apiVersion": "telemetry.istio.io/v1",
            "kind": "Telemetry",
            "metadata": {
                "name": name,
                "namespace": cluster.project,
                "labels": labels,
            },
            "spec": {"tracing": tracing},
        }
        if gateway_name is not None:
            model["spec"]["targetRefs"] = [
                {"group": "gateway.networking.k8s.io", "kind": "Gateway", "name": gateway_name}
            ]
        else:
            model["spec"]["selector"] = {"matchLabels": selector}

        return cls(model, context=cluster.context)

    @classmethod
    def supports_field(cls, cluster: KubernetesClient, field: str) -> bool:
        """True if the Telemetry CRD on this cluster accepts `field` in a `spec.tracing` entry.

        Checked against the CRD schema rather than the Istio version: the field is what the API
        server actually validates against, and it survives vendors backporting features into
        older streams.
        """
        crd = cluster.do_action("get", ["-o", "yaml", f"crd/{TELEMETRY_CRD}"], parse_output=True)

        for version in crd.model.spec.versions:
            tracing = (
                version.get("schema", {})
                .get("openAPIV3Schema", {})
                .get("properties", {})
                .get("spec", {})
                .get("properties", {})
                .get("tracing", {})
            )
            if field in tracing.get("items", {}).get("properties", {}):
                return True
        return False

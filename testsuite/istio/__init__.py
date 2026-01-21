"""Istio custom resource wrappers for configuring Istio via Sail Operator."""

from typing import Optional, List, Dict
from testsuite.kubernetes import KubernetesObject, modify


class IstioCR(KubernetesObject):
    """
    Represents Istio custom resource managed by Sail Operator.

    This class wraps the Istio CR that controls the Istio control plane configuration,
    including mesh-level settings like tracing, extensionProviders, and defaultConfig.
    """

    @modify
    def set_tracing(self, service: str, port: int, provider_name: str):
        """Enable distributed tracing in Istio control plane with OpenTelemetry provider.
        Args:
            service: OTLP collector service endpoint (e.g., "jaeger-collector.tools.svc.cluster.local")
            port: OTLP collector port (typically 4317 for gRPC)
            provider_name: Unique name for the extension provider (e.g., "jaeger-otlp")
        """
        mesh_config = {
            "enableTracing": True,
            "defaultConfig": {"tracing": {}},
            "extensionProviders": [
                {
                    "name": provider_name,
                    "opentelemetry": {"port": port, "service": service},
                }
            ],
        }
        self.model.spec.setdefault("values", {})["meshConfig"] = mesh_config

    @modify
    def reset_tracing(self):
        """Disable distributed tracing in Istio control plane."""
        if "values" in self.model.spec and "meshConfig" in self.model.spec["values"]:
            self.model.spec["values"]["meshConfig"] = {
                "enableTracing": False,
                "defaultConfig": {},
                "extensionProviders": [],
            }


class Telemetry(KubernetesObject):
    """Represents Istio Telemetry custom resource for configuring observability."""

    @classmethod
    def create_instance(
        cls,
        cluster,
        name: str,
        namespace: str = "istio-system",
        labels: Optional[Dict[str, str]] = None,
    ):
        """Create a new Telemetry custom resource instance."""
        model: Dict = {
            "apiVersion": "telemetry.istio.io/v1alpha1",
            "kind": "Telemetry",
            "metadata": {
                "name": name,
                "namespace": namespace,
            },
            "spec": {},
        }

        if labels:
            model["metadata"]["labels"] = labels

        return cls(model, context=cluster.context)

    @modify
    def set_tracing(self, providers: List[Dict[str, str]], random_sampling_percentage: float = 100):
        """
        Configure distributed tracing for this Telemetry resource.
        Sets up tracing configuration including which provider(s) to use and the
        sampling rate. The provider name must match an extensionProvider defined
        in the Istio CR's meshConfig.
        """
        tracing_config = {
            "providers": providers,
            "randomSamplingPercentage": random_sampling_percentage,
        }

        self.model.spec["tracing"] = [tracing_config]

    @modify
    def reset_tracing(self):
        """Remove all tracing configuration from this Telemetry resource."""
        if "tracing" in self.model.spec:
            self.model.spec["tracing"] = []

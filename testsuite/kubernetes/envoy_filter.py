"""Module containing Istio's EnvoyFilter related class"""

from testsuite.kubernetes import KubernetesObject, modify
from testsuite.gateway import Gateway


class EnvoyFilter(KubernetesObject):
    """Istio EnvoyFilter object for patching Envoy proxy configuration"""

    @classmethod
    def create_instance(
        cls,
        cluster,
        name,
        gateway: Gateway,
        labels: dict[str, str] = None,
    ):
        """Creates new instance of EnvoyFilter targeting a Gateway"""
        model: dict = {
            "apiVersion": "networking.istio.io/v1alpha3",
            "kind": "EnvoyFilter",
            "metadata": {
                "name": name,
                "namespace": cluster.project,
                "labels": labels,
            },
            "spec": {
                "targetRefs": [gateway.reference],
                "configPatches": [],
            },
        }

        return cls(model, context=cluster.context)

    @modify
    def add_client_cert_validation(self, port_number: int, ca_cert_path: str):
        """Adds a configPatch that enables client certificate validation on a listener"""
        self.model.spec.configPatches.append(
            {
                "applyTo": "FILTER_CHAIN",
                "match": {
                    "context": "GATEWAY",
                    "listener": {
                        "portNumber": port_number,
                    },
                },
                "patch": {
                    "operation": "MERGE",
                    "value": {
                        "transport_socket": {
                            "name": "envoy.transport_sockets.tls",
                            "typed_config": {
                                "@type": "type.googleapis.com/envoy.extensions.transport_sockets."
                                "tls.v3.DownstreamTlsContext",
                                "requireClientCertificate": True,
                                "commonTlsContext": {
                                    "validationContext": {
                                        "trusted_ca": {
                                            "filename": ca_cert_path,
                                        }
                                    }
                                },
                            },
                        }
                    },
                },
            }
        )

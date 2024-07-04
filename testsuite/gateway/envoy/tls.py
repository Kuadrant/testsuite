"""Envoy Gateway implementation with TLS setup"""

from typing import TYPE_CHECKING

import yaml

from testsuite.kubernetes.deployment import Deployment, SecretVolume, VolumeMount
from . import Envoy, EnvoyConfig

if TYPE_CHECKING:
    from testsuite.kubernetes.client import KubernetesClient

TLS_TRANSPORT = """
name: envoy.transport_sockets.tls
typed_config:
  "@type": type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.DownstreamTlsContext
  require_client_certificate: true
  common_tls_context:
    tls_certificates:
    - certificate_chain: {filename: "/etc/ssl/certs/envoy/tls.crt"}
      private_key: {filename: "/etc/ssl/certs/envoy/tls.key"}
    validation_context:
      trusted_ca:
        filename: "/etc/ssl/certs/envoy-ca/tls.crt"
"""

UPSTREAM_TLS_TRANSPORT = """
name: envoy.transport_sockets.tls
typed_config:
  "@type": type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.UpstreamTlsContext
  common_tls_context:
    validation_context:
      trusted_ca:
        filename: /etc/ssl/certs/authorino-ca/tls.crt
"""


class TLSEnvoy(Envoy):
    """Envoy setup with TLS"""

    def __init__(
        self,
        cluster: "KubernetesClient",
        name,
        authorino,
        image,
        authorino_ca_secret,
        envoy_ca_secret,
        envoy_cert_secret,
        labels: dict[str, str],
    ) -> None:
        super().__init__(cluster, name, authorino, image, labels)
        self.authorino_ca_secret = authorino_ca_secret
        self.backend_ca_secret = envoy_ca_secret
        self.envoy_cert_secret = envoy_cert_secret

    @property
    def config(self):
        if not self._config:
            self._config = EnvoyConfig.create_instance(self.cluster, self.name, self.authorino, self.labels)
            config = yaml.safe_load(self._config["envoy.yaml"])
            config["static_resources"]["listeners"][0]["filter_chains"][0]["transport_socket"] = yaml.safe_load(
                TLS_TRANSPORT
            )
            for cluster in config["static_resources"]["clusters"]:
                if cluster["name"] == "external_auth":
                    cluster["transport_socket"] = yaml.safe_load(UPSTREAM_TLS_TRANSPORT)
            self._config["envoy.yaml"] = yaml.dump(config)
        return self._config

    def create_deployment(self) -> Deployment:
        deployment = super().create_deployment()
        deployment.add_volume(SecretVolume(secret_name=self.authorino_ca_secret, name="authorino-ca"))
        deployment.add_volume(SecretVolume(secret_name=self.backend_ca_secret, name="envoy-ca"))
        deployment.add_volume(SecretVolume(secret_name=self.envoy_cert_secret, name="envoy-cert"))

        deployment.add_mount(VolumeMount(mountPath="/etc/ssl/certs/authorino-ca", name="authorino-ca"))
        deployment.add_mount(VolumeMount(mountPath="/etc/ssl/certs/envoy-ca", name="envoy-ca"))
        deployment.add_mount(VolumeMount(mountPath="/etc/ssl/certs/envoy", name="envoy-cert"))

        return deployment

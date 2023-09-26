"""Envoy Gateway implementation with TLS setup"""
from importlib import resources
from typing import TYPE_CHECKING

import yaml

from . import Envoy, EnvoyConfig

if TYPE_CHECKING:
    from ...client import OpenShiftClient

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
        filename: /etc/ssl/certs/authorino/tls.crt
"""


class TLSEnvoy(Envoy):
    """Envoy setup with TLS"""

    def __init__(
        self,
        openshift: "OpenShiftClient",
        name,
        authorino,
        image,
        authorino_ca_secret,
        envoy_ca_secret,
        envoy_cert_secret,
        labels: dict[str, str],
    ) -> None:
        super().__init__(openshift, name, authorino, image, labels)
        self.authorino_ca_secret = authorino_ca_secret
        self.backend_ca_secret = envoy_ca_secret
        self.envoy_cert_secret = envoy_cert_secret

    @property
    def config(self):
        if not self._config:
            self._config = EnvoyConfig.create_instance(self.openshift, self.name, self.authorino, self.labels)
            config = yaml.safe_load(self._config["envoy.yaml"])
            config["static_resources"]["listeners"][0]["filter_chains"][0]["transport_socket"] = yaml.safe_load(
                TLS_TRANSPORT
            )
            for cluster in config["static_resources"]["clusters"]:
                if cluster["name"] == "external_auth":
                    cluster["transport_socket"] = yaml.safe_load(UPSTREAM_TLS_TRANSPORT)
            self._config["envoy.yaml"] = yaml.dump(config)
        return self._config

    def commit(self):
        self.config.commit()
        self.envoy_objects = self.openshift.new_app(
            resources.files("testsuite.resources.tls").joinpath("envoy.yaml"),
            {
                "NAME": self.name,
                "LABEL": self.app_label,
                "AUTHORINO_CA_SECRET": self.authorino_ca_secret,
                "ENVOY_CA_SECRET": self.backend_ca_secret,
                "ENVOY_CERT_SECRET": self.envoy_cert_secret,
                "ENVOY_IMAGE": self.image,
            },
        )

        with self.openshift.context:
            assert self.openshift.is_ready(self.envoy_objects.narrow("deployment")), "Envoy wasn't ready in time"

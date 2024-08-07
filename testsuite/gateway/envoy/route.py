"""GatewayRoute implementation for pure Envoy Deployment"""

import typing

from testsuite.gateway import Gateway, GatewayRoute

if typing.TYPE_CHECKING:
    from testsuite.kubernetes.client import KubernetesClient
    from testsuite.backend import Backend
    from testsuite.kuadrant.policy.authorization.auth_config import AuthConfig


class EnvoyVirtualRoute(GatewayRoute):
    """Simulated equivalent of HttpRoute for pure Envoy deployments"""

    @property
    def reference(self) -> dict[str, str]:
        raise AttributeError("Not Supported for Envoy-only deployment")

    @classmethod
    def create_instance(cls, cluster: "KubernetesClient", name, gateway: Gateway, labels: dict[str, str] = None):
        return cls(cluster, gateway)

    def __init__(self, cluster, gateway) -> None:
        super().__init__()
        self.cluster = cluster
        self.gateway = gateway
        self.auth_configs: list["AuthConfig"] = []
        self.hostnames: list[str] = []

    def add_backend(self, backend: "Backend", prefix="/"):
        if not self.gateway.config.has_backend(backend, prefix):
            self.gateway.config.add_backend(backend, prefix)
            self.gateway.rollout()

    def remove_all_backend(self):
        self.gateway.config.remove_all_backends()
        self.gateway.rollout()

    # Hostname manipulation is not supported with Envoy, Envoy accepts all hostnames
    def add_hostname(self, hostname: str):
        self.hostnames.append(hostname)
        for auth_config in self.auth_configs:
            auth_config.add_host(hostname)

    def remove_hostname(self, hostname: str):
        self.hostnames.remove(hostname)
        for auth_config in self.auth_configs:
            auth_config.remove_host(hostname)

    def remove_all_hostnames(self):
        self.hostnames.clear()
        for auth_config in self.auth_configs:
            auth_config.remove_all_hosts()

    def add_auth_config(self, auth_config: "AuthConfig"):
        """Adds AuthConfig to this virtual route"""
        self.auth_configs.append(auth_config)
        for hostname in self.hostnames:
            auth_config.add_host(hostname)

    def commit(self):
        return

    def delete(self):
        return

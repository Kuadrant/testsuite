"""Envoy Config"""
import yaml

from testsuite.openshift.httpbin import Httpbin
from testsuite.openshift import modify
from testsuite.openshift.config_map import ConfigMap


BASE_CONFIG = """
      static_resources:
        listeners:
        - address:
            socket_address:
              address: 0.0.0.0
              port_value: 8000
          filter_chains:
          - filters:
            - name: envoy.http_connection_manager
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                stat_prefix: local
                route_config:
                  name: local_route
                  virtual_hosts:
                  - name: local_service
                    domains: ['*']
                    typed_per_filter_config:
                      envoy.filters.http.ext_authz:
                        "@type": type.googleapis.com/envoy.extensions.filters.http.ext_authz.v3.ExtAuthzPerRoute
                        check_settings:
                          context_extensions:
                            virtual_host: local_service
                    routes: []
                http_filters:
                - name: envoy.filters.http.ext_authz
                  typed_config:
                    "@type": type.googleapis.com/envoy.extensions.filters.http.ext_authz.v3.ExtAuthz
                    transport_api_version: V3
                    failure_mode_allow: false
                    status_on_error: {code: 500}
                    include_peer_certificate: true
                    grpc_service:
                      envoy_grpc:
                        cluster_name: external_auth
                      timeout: 1s
                - name: envoy.filters.http.router
                  typed_config:
                    "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
                use_remote_address: true
        clusters:
        - name: external_auth
          connect_timeout: 0.25s
          type: strict_dns
          lb_policy: round_robin
          load_assignment:
            cluster_name: external_auth
            endpoints:
            - lb_endpoints:
              - endpoint:
                  address:
                    socket_address:
                      address: ${authorino_url}
                      port_value: 50051
          typed_extension_protocol_options:
            envoy.extensions.upstreams.http.v3.HttpProtocolOptions:
              "@type": type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions
              upstream_http_protocol_options:
                auto_sni: true
              explicit_http_config:
                http2_protocol_options: {}
      admin:
        address:
          socket_address:
            address: 0.0.0.0
            port_value: 8001
"""

CLUSTER = """
name: ${backend_url}
connect_timeout: 0.25s
type: strict_dns
lb_policy: round_robin
load_assignment:
  cluster_name: ${backend_url}
  endpoints:
  - lb_endpoints:
    - endpoint:
        address:
          socket_address:
            address: ${backend_url}
            port_value: 8080
"""


class EnvoyConfig(ConfigMap):
    """ConfigMap containing Envoy configuration"""

    @classmethod
    def create_instance(
        cls, openshift, name, authorino, labels: dict[str, str] = None
    ):  # pylint: disable=arguments-renamed
        return super().create_instance(
            openshift,
            name,
            {"envoy.yaml": BASE_CONFIG.replace("${authorino_url}", authorino.authorization_url)},
            labels,
        )

    @modify
    def add_backend(self, backend: Httpbin, prefix: str):
        """Adds backend to the EnvoyConfig"""
        config = yaml.safe_load(self["envoy.yaml"])
        config["static_resources"]["clusters"].append(yaml.safe_load(CLUSTER.replace("${backend_url}", backend.url)))
        config["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"]["route_config"][
            "virtual_hosts"
        ][0]["routes"].append({"match": {"prefix": prefix}, "route": {"cluster": backend.url}})
        self["envoy.yaml"] = yaml.dump(config)

    @modify
    def remove_all_backends(self):
        """Removes all backends from EnvoyConfig"""
        config = yaml.safe_load(self["envoy.yaml"])
        clusters = config["static_resources"]["clusters"]
        for cluster in clusters:
            if cluster["name"] != "external_auth":
                clusters.remove(cluster)
        config["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"]["route_config"][
            "virtual_hosts"
        ][0]["routes"] = {}
        self["envoy.yaml"] = yaml.dump(config)

"""JWT plain identity test Envoy"""

from urllib.parse import urlparse
import yaml

from testsuite.gateway.envoy import Envoy, EnvoyConfig


class JwtEnvoy(Envoy):
    """Envoy configuration with JWT tests setup"""

    def __init__(
        self,
        cluster,
        gw_name,
        authorino,
        envoy_image,
        keycloak_realm,
        keycloak_url,
        labels: dict[str, str],
    ):
        super().__init__(cluster, gw_name, authorino, envoy_image, labels)
        self.server_url = keycloak_url
        self.realm = keycloak_realm

    @property
    def config(self):
        if not self._config:
            self._config = EnvoyConfig.create_instance(self.cluster, self.name, self.authorino, self.labels)
            config = yaml.safe_load(self._config["envoy.yaml"])
            config["static_resources"]["clusters"].append(
                {
                    "name": "keycloak",
                    "connect_timeout": "0.25s",
                    "type": "logical_dns",
                    "lb_policy": "round_robin",
                    "load_assignment": {
                        "cluster_name": "keycloak",
                        "endpoints": [
                            {
                                "lb_endpoints": [
                                    {
                                        "endpoint": {
                                            "address": {
                                                "socket_address": {
                                                    "address": urlparse(self.server_url).hostname,
                                                    "port_value": urlparse(self.server_url).port,
                                                }
                                            }
                                        }
                                    }
                                ]
                            }
                        ],
                    },
                }
            )
            config["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"][
                "http_filters"
            ].insert(
                0,
                {
                    "name": "envoy.filters.http.jwt_authn",
                    "typed_config": {
                        "@type": "type.googleapis.com/envoy.extensions.filters.http.jwt_authn.v3.JwtAuthentication",
                        "providers": {
                            "keycloak": {
                                "issuer": f"{self.server_url}/realms/{self.realm}",
                                "remote_jwks": {
                                    "http_uri": {
                                        "uri": f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/certs",
                                        "cluster": "keycloak",
                                        "timeout": "5s",
                                    },
                                    "cache_duration": {"seconds": 300},
                                },
                                "payload_in_metadata": "verified_jwt",
                            }
                        },
                        "rules": [{"match": {"prefix": "/"}, "requires": {"provider_name": "keycloak"}}],
                    },
                },
            )
            config["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"][
                "http_filters"
            ][1]["typed_config"]["metadata_context_namespaces"] = ["envoy.filters.http.jwt_authn"]
            self._config["envoy.yaml"] = yaml.dump(config)
        return self._config

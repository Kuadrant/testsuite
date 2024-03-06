"""Wristband Envoy"""

import yaml

from testsuite.gateway.envoy import Envoy, EnvoyConfig


class WristbandEnvoy(Envoy):
    """Envoy configuration with Wristband setup"""

    @property
    def config(self):
        if not self._config:
            self._config = EnvoyConfig.create_instance(self.openshift, self.name, self.authorino, self.labels)
            config = yaml.safe_load(self._config["envoy.yaml"])
            config["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"][
                "route_config"
            ]["virtual_hosts"][0]["routes"].append(
                {
                    "match": {"prefix": "/auth"},
                    "directResponse": {"status": 200},
                    "response_headers_to_add": [
                        {
                            "header": {
                                "key": "wristband-token",
                                "value": '%DYNAMIC_METADATA(["envoy.filters.http.ext_authz", "wristband"])%',
                            }
                        }
                    ],
                }
            )
            self._config["envoy.yaml"] = yaml.dump(config)
        return self._config

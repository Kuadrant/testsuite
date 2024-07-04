"""Kubernetes Ingress object"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from testsuite.kubernetes import KubernetesObject

if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from testsuite.kubernetes.client import KubernetesClient


class Ingress(KubernetesObject):
    """Represents Kubernetes Ingress object"""

    @classmethod
    def create_instance(
        cls,
        cluster: "KubernetesClient",
        name,
        rules: Optional[List[Dict[str, Any]]] = None,
        tls: Optional[List[Dict[str, Any]]] = None,
    ):
        """Creates base instance"""
        if rules is None:
            rules = []

        if tls is None:
            tls = []

        model: Dict[str, Any] = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {"name": name, "namespace": cluster.project},
            "spec": {"rules": rules, "tls": tls},
        }

        with cluster.context:
            return cls(model)

    @classmethod
    def create_service_ingress(
        cls, cluster: "KubernetesClient", name, service_name, port_number=80, path="/", path_type="Prefix", host=None
    ):
        """
        Creates Ingress instance for service without tls configured
        """
        rule = {
            "http": {
                "paths": [
                    {
                        "backend": {"service": {"name": service_name, "port": {"number": port_number}}},
                        "path": path,
                        "pathType": path_type,
                    },
                ]
            }
        }

        if host is not None:
            rule["host"] = host

        return cls.create_instance(cluster, name, rules=[rule])

    @property
    def rules(self):
        """Returns rules defined in the ingress"""
        return self.model.spec.rules

    def wait_for_hosts(self):
        """Waits until all rules within the ingress have host fields filled"""

        def _all_rules_have_host(obj):
            return all("host" in r and len(r.get("host")) > 0 for r in obj.model.spec.rules)

        success = self.wait_until(_all_rules_have_host)

        return success

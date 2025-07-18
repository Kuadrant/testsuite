"""APIService object for Kubernetes"""

from testsuite.kubernetes import KubernetesObject


class APIService(KubernetesObject):
    """Kubernetes APIService"""

    @classmethod
    def create_instance(
        cls,
        cluster,
        name: str,
        service_name: str,
        service_namespace: str,
        group: str,
        version: str,
        labels: dict[str, str] = None,
        insecure_skip_tls_verify: bool = False,
        group_priority_minimum: int = 100,
        version_priority: int = 100,
    ):
        """Creates a new APIService object"""
        model: dict = {
            "kind": "APIService",
            "apiVersion": "apiregistration.k8s.io/v1",
            "metadata": {
                "name": name,
                "labels": labels,
            },
            "spec": {
                "service": {
                    "name": service_name,
                    "namespace": service_namespace,
                },
                "group": group,
                "version": version,
                "insecureSkipTLSVerify": insecure_skip_tls_verify,
                "groupPriorityMinimum": group_priority_minimum,
                "versionPriority": version_priority,
            },
        }
        return cls(model, context=cluster.context)

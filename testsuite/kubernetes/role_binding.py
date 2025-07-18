"""RoleBinding object for Kubernetes"""

from testsuite.kubernetes import KubernetesObject


class RoleBinding(KubernetesObject):
    """Kubernetes RoleBinding"""

    @classmethod
    def create_instance(
        cls,
        cluster,
        name,
        role: str,
        serviceaccounts: list[str],
        labels: dict[str, str] = None,
    ):
        """Creates a new RoleBinding object"""
        model: dict = {
            "kind": "RoleBinding",
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "metadata": {
                "name": name,
                "labels": labels,
            },
            "roleRef": {
                "kind": "Role",
                "name": role,
                "apiGroup": "rbac.authorization.k8s.io",
            },
            "subjects": [
                {"kind": "ServiceAccount", "name": name, "namespace": cluster.project} for name in serviceaccounts
            ],
        }
        return cls(model, context=cluster.context)

"""ClusterRole and ClusterRoleBinding objects for Kubernetes"""

from typing import Any, Dict, List, Optional
from testsuite.kubernetes import KubernetesObject


class ClusterRole(KubernetesObject):
    """Kubernetes ClusterRole"""

    @classmethod
    def create_instance(
        cls,
        cluster,
        name,
        rules: Optional[List[Dict[str, Any]]] = None,
        labels: dict[str, str] = None,
    ):
        """Creates a new ClusterRole instance"""
        model: dict = {
            "kind": "ClusterRole",
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "metadata": {
                "name": name,
                "labels": labels,
            },
            "rules": rules,
        }
        return cls(model, context=cluster.context)


class ClusterRoleBinding(KubernetesObject):
    """Kubernetes ClusterRoleBinding"""

    @classmethod
    def create_instance(
        cls,
        cluster,
        name,
        cluster_role: str,
        serviceaccounts: List[str],
        labels: dict[str, str] = None,
    ):
        """Creates a new ClusterRoleBinding object"""
        model: dict = {
            "kind": "ClusterRoleBinding",
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "metadata": {
                "name": name,
                "labels": labels,
            },
            "roleRef": {
                "kind": "ClusterRole",
                "name": cluster_role,
            },
            "subjects": [
                {"kind": "ServiceAccount", "name": name, "namespace": cluster.project} for name in serviceaccounts
            ],
        }
        return cls(model, context=cluster.context)

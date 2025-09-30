"""Service Account object for Kubernetes"""

import yaml

import openshift_client as oc

from testsuite.kubernetes import KubernetesObject


class ServiceAccount(KubernetesObject):
    """Kubernetest ServiceAccount"""

    @classmethod
    def create_instance(cls, cluster, name: str, labels: dict[str, str] = None):
        """Creates new instance of service account"""
        model = {
            "kind": "ServiceAccount",
            "apiVersion": "v1",
            "metadata": {
                "name": name,
                "labels": labels,
            },
        }

        return cls(model, context=cluster.context)

    def get_auth_token(self, audiences: list[str] = None, duration: str = None) -> str:
        """Requests and returns bound token for service account"""
        args = ["token", self.name()]
        if audiences:
            args.extend([f"--audience={a}" for a in audiences])
        if duration:
            args.append(f"--duration={duration}")
        with self.context:
            return oc.invoke("create", args).out().strip()

    def get_kubeconfig(self, context_name, user_name, cluster_name, api_url) -> str:
        """Assembles and returns kubeconfig with service account token"""
        kubeconfig = {
            "apiVersion": "v1",
            "kind": "Config",
            "clusters": [
                {
                    "cluster": {"insecure-skip-tls-verify": True, "server": api_url},  # insecure clusters only for now
                    "name": cluster_name,
                }
            ],
            "contexts": [
                {
                    "context": {"cluster": cluster_name, "namespace": self.context.project_name, "user": user_name},
                    "name": context_name,
                }
            ],
            "current-context": context_name,
            "preferences": {},
            "users": [{"name": user_name, "user": {"token": self.get_auth_token(duration="1h")}}],
        }

        return yaml.dump(kubeconfig)

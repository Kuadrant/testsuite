"""Module for TLSPolicy related classes"""

from testsuite.gateway import Referencable
from testsuite.kubernetes.client import KubernetesClient
from testsuite.policy import Policy, has_condition


class TLSPolicy(Policy):
    """TLSPolicy object"""

    @classmethod
    def create_instance(
        cls,
        cluster: KubernetesClient,
        name: str,
        parent: Referencable,
        issuer: Referencable,
        labels: dict[str, str] = None,
        commonName: str = None,
        duration: str = None,
        usages: list[str] = None,
        algorithm: str = None,
        key_size: int = None,
    ):  # pylint: disable=invalid-name
        """Creates new instance of TLSPolicy"""

        model = {
            "apiVersion": "kuadrant.io/v1alpha1",
            "kind": "TLSPolicy",
            "metadata": {"name": name, "labels": labels},
            "spec": {
                "targetRef": parent.reference,
                "issuerRef": issuer.reference,
                "commonName": commonName,
                "duration": duration,
                "usages": usages,
                "privateKey": {
                    "algorithm": algorithm,
                    "size": key_size,
                },
            },
        }

        return cls(model, context=cluster.context)

    def __setitem__(self, key, value):
        self.model.spec[key] = value

    def __getitem__(self, key):
        return self.model.spec[key]

    def wait_for_ready(self):
        """Increase timeout to account for letsEncrypt"""
        success = self.wait_until(has_condition("Enforced", "True"), timelimit=180)
        assert success, f"{self.kind()} did not get ready in time"

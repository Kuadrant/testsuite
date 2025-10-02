"""Module containing Secret related classes"""

import base64
from typing import Literal

from testsuite.certificates import Certificate
from testsuite.kubernetes import KubernetesObject


class Secret(KubernetesObject):
    """Kubernetes Secret object"""

    @classmethod
    def create_instance(
        cls,
        cluster,
        name,
        stringData: dict[str, str] = None,  # pylint: disable=invalid-name
        data: dict[str, str] = None,
        secret_type: Literal["kubernetes.io/tls", "kuadrant.io/aws", "kuadrant.io/coredns", "Opaque"] = "Opaque",
        labels: dict[str, str] = None,
    ):
        """Creates new Secret"""
        if not (stringData is None) ^ (data is None):
            raise AttributeError("Either `stringData` or `data` must be used for the secret creation")

        model: dict = {
            "kind": "Secret",
            "apiVersion": "v1",
            "metadata": {
                "name": name,
                "labels": labels,
            },
            "type": secret_type,
        }

        if stringData:
            model["stringData"] = stringData

        if data:
            model["data"] = data

        return cls(model, context=cluster.context)

    def __getitem__(self, name):
        return base64.b64decode(self.model.data[name]).decode("utf-8")

    def __contains__(self, name):
        return name in self.model.data

    def __setitem__(self, name, value):
        self.model.data[name] = base64.b64encode(value).decode("utf-8")


class TLSSecret(Secret):
    """Kubernetes TLS Secret"""

    # pylint: disable=arguments-renamed
    @classmethod
    def create_instance(  # type: ignore[override]
        cls,
        cluster,
        name,
        certificate: Certificate,
        cert_name: str = "tls.crt",
        key_name: str = "tls.key",
        secret_type: Literal["kubernetes.io/tls", "kuadrant.io/aws", "Opaque"] = "kubernetes.io/tls",
        labels: dict[str, str] = None,
    ):
        return super().create_instance(
            cluster,
            name,
            stringData={
                cert_name: certificate.chain,
                key_name: certificate.key,
            },
            secret_type=secret_type,
            labels=labels,
        )

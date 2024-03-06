"""Module containing Secret related classes"""

import base64
from typing import Literal

from testsuite.certificates import Certificate
from testsuite.openshift import OpenShiftObject


class Secret(OpenShiftObject):
    """Kubernetes Secret object"""

    @classmethod
    def create_instance(
        cls,
        openshift,
        name,
        data: dict[str, str],
        secret_type: Literal["kubernetes.io/tls", "Opaque"] = "Opaque",
        labels: dict[str, str] = None,
    ):
        """Creates new Secret"""
        model: dict = {
            "kind": "Secret",
            "apiVersion": "v1",
            "metadata": {
                "name": name,
                "labels": labels,
            },
            "stringData": data,
            "type": secret_type,
        }
        return cls(model, context=openshift.context)

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
        openshift,
        name,
        certificate: Certificate,
        cert_name: str = "tls.crt",
        key_name: str = "tls.key",
        secret_type: Literal["kubernetes.io/tls", "Opaque"] = "kubernetes.io/tls",
        labels: dict[str, str] = None,
    ):
        return super().create_instance(
            openshift,
            name,
            {
                cert_name: certificate.chain,
                key_name: certificate.key,
            },
            secret_type,
            labels,
        )

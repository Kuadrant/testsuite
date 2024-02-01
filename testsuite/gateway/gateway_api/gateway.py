"""Module containing all gateway classes"""

# mypy: disable-error-code="override"
import json
from typing import Optional

import openshift_client as oc

from testsuite.certificates import Certificate
from testsuite.gateway import Gateway
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift import OpenShiftObject


class KuadrantGateway(OpenShiftObject, Gateway):
    """Gateway object for purposes of MGC"""

    @classmethod
    def create_instance(cls, openshift: OpenShiftClient, name, hostname, labels):
        """Creates new instance of Gateway"""

        model = {
            "apiVersion": "gateway.networking.k8s.io/v1beta1",
            "kind": "Gateway",
            "metadata": {"name": name, "labels": labels},
            "spec": {
                "gatewayClassName": "istio",
                "listeners": [
                    {
                        "name": "api",
                        "port": 80,
                        "protocol": "HTTP",
                        "hostname": hostname,
                        "allowedRoutes": {"namespaces": {"from": "All"}},
                    }
                ],
            },
        }

        return cls(model, context=openshift.context)

    @property
    def service_name(self) -> str:
        return f"{self.name()}-istio"

    @property
    def openshift(self):
        """Hostname of the first listener"""
        return OpenShiftClient.from_context(self.context)

    def is_ready(self):
        """Check the programmed status"""
        for condition in self.model.status.conditions:
            if condition.type == "Programmed" and condition.status == "True":
                return True
        return False

    def wait_for_ready(self, timeout: int = 180):
        """Waits for the gateway to be ready in the sense of is_ready(self)"""
        with oc.timeout(timeout):
            success, _, _ = self.self_selector().until_all(success_func=lambda obj: MGCGateway(obj.model).is_ready())
            assert success, "Gateway didn't get ready in time"
            self.refresh()

    def get_tls_cert(self):
        return None

    @property
    def reference(self):
        return {
            "group": "gateway.networking.k8s.io",
            "kind": "Gateway",
            "name": self.name(),
            "namespace": self.namespace(),
        }


class MGCGateway(KuadrantGateway):
    """Gateway object for purposes of MGC"""

    @classmethod
    def create_instance(
        cls,
        openshift: OpenShiftClient,
        name: str,
        gateway_class: str,
        hostname: str,
        labels: dict[str, str] = None,
        tls: bool = True,
        placement: str = None,
    ):  # pylint: disable=arguments-renamed
        """Creates new instance of Gateway"""
        if labels is None:
            labels = {}

        if placement is not None:
            labels["cluster.open-cluster-management.io/placement"] = placement

        instance = super(MGCGateway, cls).create_instance(openshift, name, hostname, labels)
        instance.model.spec.gatewayClassName = gateway_class
        if tls:
            instance.model.spec.listeners = [
                {
                    "name": "api",
                    "port": 443,
                    "protocol": "HTTPS",
                    "hostname": hostname,
                    "allowedRoutes": {"namespaces": {"from": "All"}},
                    "tls": {
                        "mode": "Terminate",
                        "certificateRefs": [{"name": f"{name}-tls", "kind": "Secret"}],
                    },
                }
            ]

        return instance

    def get_tls_cert(self) -> Optional[Certificate]:
        """Returns TLS certificate used by the gateway"""
        if "tls" not in self.model.spec.listeners[0]:
            return None

        tls_cert_secret_name = self.cert_secret_name
        tls_cert_secret = self.openshift.get_secret(tls_cert_secret_name)
        tls_cert = Certificate(
            key=tls_cert_secret["tls.key"],
            certificate=tls_cert_secret["tls.crt"],
            chain=tls_cert_secret["ca.crt"],
        )
        return tls_cert

    def delete_tls_secret(self):
        """Deletes secret with TLS certificate used by the gateway"""
        with self.openshift.context:
            oc.selector(f"secret/{self.cert_secret_name}").delete(ignore_not_found=True)

    def get_spoke_gateway(self, spokes: dict[str, OpenShiftClient]) -> "MGCGateway":
        """
        Returns spoke gateway on an arbitrary, and sometimes, random spoke cluster.
        Works only for GW deployed on Hub
        """
        self.refresh()
        cluster_name = json.loads(self.model.metadata.annotations["kuadrant.io/gateway-clusters"])[0]
        spoke_client = spokes[cluster_name]
        prefix = "kuadrant"
        spoke_client = spoke_client.change_project(f"{prefix}-{self.namespace()}")
        with spoke_client.context:
            return oc.selector(f"gateway/{self.name()}").object(cls=self.__class__)

    @property
    def cert_secret_name(self):
        """Returns name of the secret with generated TLS certificate"""
        return self.model.spec.listeners[0].tls.certificateRefs[0].name

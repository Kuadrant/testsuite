"""Module containing all gateway classes"""

from typing import Any

import openshift_client as oc

from testsuite.certificates import Certificate
from testsuite.gateway import Gateway
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift import OpenShiftObject
from testsuite.openshift.service import Service


class KuadrantGateway(OpenShiftObject, Gateway):
    """Gateway object for Kuadrant"""

    @classmethod
    def create_instance(cls, openshift: OpenShiftClient, name, hostname, labels, tls=False):
        """Creates new instance of Gateway"""

        model: dict[Any, Any] = {
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

        if tls:
            model["spec"]["listeners"] = [
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

        return cls(model, context=openshift.context)

    @property
    def service_name(self) -> str:
        return f"{self.name()}-istio"

    def external_ip(self) -> str:
        with self.context:
            return f"{self.refresh().model.status.addresses[0].value}:80"

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
            success, _, _ = self.self_selector().until_all(
                success_func=lambda obj: self.__class__(obj.model).is_ready()
            )
            assert success, "Gateway didn't get ready in time"
            self.refresh()

    def get_tls_cert(self):
        if "tls" not in self.model.spec.listeners[0]:
            return None

        tls_cert_secret_name = self.cert_secret_name
        tls_cert_secret = self.openshift.get_secret(tls_cert_secret_name)
        tls_cert = Certificate(
            key=tls_cert_secret["tls.key"],
            certificate=tls_cert_secret["tls.crt"],
            chain=tls_cert_secret["ca.crt"] if "ca.crt" in tls_cert_secret else None,
        )
        return tls_cert

    def delete(self, ignore_not_found=True, cmd_args=None):
        res = super().delete(ignore_not_found, cmd_args)
        with self.openshift.context:
            # TLSPolicy does not delete certificates it creates
            oc.selector(f"secret/{self.cert_secret_name}").delete(ignore_not_found=True)
            # Istio does not delete ServiceAccount
            oc.selector(f"sa/{self.service_name}").delete(ignore_not_found=True)
        return res

    @property
    def cert_secret_name(self):
        """Returns name of the secret with generated TLS certificate"""
        return self.model.spec.listeners[0].tls.certificateRefs[0].name

    @property
    def reference(self):
        return {
            "group": "gateway.networking.k8s.io",
            "kind": "Gateway",
            "name": self.name(),
            "namespace": self.namespace(),
        }

"""Module containing all gateway classes"""

from time import sleep
from typing import Any

import openshift_client as oc

from testsuite.config import settings
from testsuite.certificates import Certificate
from testsuite.gateway import Gateway, GatewayListener
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kubernetes import KubernetesObject, modify
from testsuite.kuadrant.policy import Policy
from testsuite.utils import check_condition, asdict, domain_match


class KuadrantGateway(KubernetesObject, Gateway):
    """Gateway object for Kuadrant"""

    @classmethod
    def create_instance(cls, cluster: KubernetesClient, name, labels):
        """Creates new instance of Gateway"""

        model: dict[Any, Any] = {
            "apiVersion": "gateway.networking.k8s.io/v1beta1",
            "kind": "Gateway",
            "metadata": {"name": name, "labels": labels},
            "spec": {"gatewayClassName": "istio", "listeners": []},
        }
        gateway = cls(model, context=cluster.context)
        return gateway

    @modify
    def add_listener(self, listener: GatewayListener):
        """Adds a listener to Gateway."""
        self.model.spec.listeners.append(asdict(listener))

    @modify
    def remove_listener(self, listener_name: str):
        """Removes a listener from Gateway."""
        self.model.spec.listeners = list(filter(lambda i: i["name"] != listener_name, self.model.spec.listeners))

    def get_listener_dns_ttl(self, listener_name: str) -> int:
        """Returns TTL stored in DNSRecord CR under the specified Listener."""
        dns_record = self.cluster.do_action(
            "get", ["-o", "yaml", f"dnsrecords.kuadrant.io/{self.name()}-{listener_name}"], parse_output=True
        )
        return dns_record.model.spec.endpoints[0].recordTTL

    @property
    def service_name(self) -> str:
        return f"{self.name()}-istio"

    def external_ip(self) -> str:
        with self.context:
            return f"{self.refresh().model.status.addresses[0].value}:80"

    @property
    def cluster(self):
        """Hostname of the first listener"""
        return KubernetesClient.from_context(self.context)

    def is_ready(self):
        """Check the programmed status"""
        for condition in self.model.status.conditions:
            if condition.type == "Programmed" and condition.status == "True":
                return True
        return False

    def wait_for_ready(self, timeout: int = 10 * 60):
        """Waits for the gateway to be ready in the sense of is_ready(self)"""
        success = self.wait_until(lambda obj: self.__class__(obj.model).is_ready(), timelimit=timeout)
        assert success, "Gateway didn't get ready in time"
        if settings["control_plane"]["slow_loadbalancers"]:
            sleep(60)

    def is_affected_by(self, policy: Policy) -> bool:
        """Returns True, if affected by status is found within the object for the specific policy"""
        for condition in self.model.status.conditions:
            if check_condition(
                condition,
                f"kuadrant.io/{policy.kind(lowercase=False)}Affected",
                "True",
                "Accepted",
                f"Object affected by {policy.kind(lowercase=False)}",
                f"{policy.namespace()}/{policy.name()}",
            ):
                return True
        return False

    def get_tls_cert(self, hostname):
        tls_cert_secret_name = None
        for listener in self.all_tls_listeners():
            if domain_match(hostname, listener.hostname):
                tls_cert_secret_name = listener.tls.certificateRefs[0].name

        if tls_cert_secret_name is None:
            return None

        try:
            tls_cert_secret = self.cluster.get_secret(tls_cert_secret_name)
        except oc.OpenShiftPythonException as e:
            if "Expected a single object, but selected 0" in e.msg:
                raise oc.OpenShiftPythonException("TLS secret was not created") from None
            raise e
        tls_cert = Certificate(
            key=tls_cert_secret["tls.key"],
            certificate=tls_cert_secret["tls.crt"],
            chain=tls_cert_secret["ca.crt"] if "ca.crt" in tls_cert_secret else None,
        )
        return tls_cert

    def all_tls_listeners(self):
        """Yields all listeners in gateway that support 'tls'"""
        for listener in self.model.spec.listeners:
            if "tls" in listener:
                yield listener

    def delete(self, ignore_not_found=True, cmd_args=None):
        res = super().delete(ignore_not_found, cmd_args)
        with self.cluster.context:
            # TLSPolicy does not delete certificates it creates
            for secret in oc.selector("secret").objects():
                if "tls" in secret.name() and self.name() in secret.name():
                    secret.delete()

            # Istio does not delete ServiceAccount
            oc.selector(f"sa/{self.service_name}").delete(ignore_not_found=True)
        return res

    @property
    def reference(self):
        return {
            "group": "gateway.networking.k8s.io",
            "kind": "Gateway",
            "name": self.name(),
        }

"""Module for DNSPolicy related classes"""

from dataclasses import dataclass
from typing import Optional, Literal

import openshift_client as oc

from testsuite.gateway import Referencable
from testsuite.kubernetes import KubernetesObject
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kuadrant.policy import Policy
from testsuite.utils import asdict, check_condition


def has_record_condition(condition_type, status="True", reason=None, message=None):
    """Returns function, that returns True if the DNSPolicy has specific record condition"""

    def _check(obj):
        for record in obj.model.status.recordConditions.values():
            for condition in record:
                if check_condition(condition, condition_type, status, reason, message):
                    return True
        return False

    return _check


@dataclass
class LoadBalancing:
    """Dataclass for DNSPolicy load-balancing spec"""

    defaultGeo: bool  # pylint: disable=invalid-name
    geo: str
    weight: Optional[int] = None


@dataclass
class AdditionalHeadersRef:
    """Object representing DNSPolicy additionalHeadersRef field"""

    name: str


@dataclass
class HealthCheck:  # pylint: disable=invalid-name
    """Object representing DNSPolicy health check specification"""

    additionalHeadersRef: Optional[AdditionalHeadersRef] = None
    path: Optional[str] = None
    failureThreshold: Optional[int] = None
    interval: Optional[str] = None
    port: Optional[int] = None
    protocol: Literal["HTTP", "HTTPS"] = "HTTP"


class DNSHealthCheckProbe(KubernetesObject):
    """DNSHealthCheckProbe object"""

    def _status_ready(self):
        """Returns True if DNSHealthCheckProbe status.healthy field has appeared"""
        return self.wait_until(lambda obj: obj.model.status.healthy is not oc.Missing)

    def is_healthy(self) -> bool:
        """Returns True if DNSHealthCheckProbe endpoint is healthy"""
        assert self._status_ready(), "DNSHealthCheckProbe status wasn't ready in time"
        return self.refresh().model.status.healthy


class DNSPolicy(Policy):
    """DNSPolicy object"""

    @classmethod
    def create_instance(
        cls,
        cluster: KubernetesClient,
        name: str,
        parent: Referencable,
        provider_secret_name: str,
        load_balancing: LoadBalancing = None,
        labels: dict[str, str] = None,
    ):
        """Creates new instance of DNSPolicy"""

        model: dict = {
            "apiVersion": "kuadrant.io/v1",
            "kind": "DNSPolicy",
            "metadata": {"name": name, "labels": labels},
            "spec": {
                "targetRef": parent.reference,
                "providerRefs": [{"name": provider_secret_name}],
            },
        }

        if load_balancing:
            model["spec"]["loadBalancing"] = asdict(load_balancing)

        return cls(model, context=cluster.context)

    def set_health_check(self, health_check: HealthCheck):
        """Sets health check for DNSPolicy"""
        self.model["spec"]["healthCheck"] = asdict(health_check)

    def _get_dns_record(self):
        """Returns DNSRecord object for the created DNSPolicy"""
        with self.context:
            assert self.wait_until(
                lambda obj: len(obj.get_owned("dnsrecords.kuadrant.io")) > 0
            ), "The corresponding DNSRecord object wasn't created in time"
            dns_record = self.get_owned("dnsrecords.kuadrant.io")[0]
        return KubernetesObject(dns_record.model, context=self.context)

    def get_dns_health_probe(self) -> DNSHealthCheckProbe:
        """Returns DNSHealthCheckProbe object for the created DNSPolicy"""
        dns_record = self._get_dns_record()
        with self.context:
            assert dns_record.wait_until(
                lambda obj: len(obj.get_owned("DNSHealthCheckProbe")) > 0
            ), "The corresponding DNSHealthCheckProbe object wasn't created in time"
            dns_probe = dns_record.get_owned("DNSHealthCheckProbe")[0]
        return DNSHealthCheckProbe(dns_probe.model, context=self.context)

    def wait_for_full_enforced(self, timelimit=300):
        """Wait for a Policy to be fully Enforced with increased timelimit for DNSPolicy"""
        super().wait_for_full_enforced(timelimit=timelimit)

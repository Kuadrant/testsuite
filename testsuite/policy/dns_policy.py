"""Module for DNSPolicy related classes"""

from dataclasses import dataclass
from typing import Optional, Literal

import openshift_client as oc

from testsuite.utils import asdict
from testsuite.gateway import Referencable
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift import OpenShiftObject


@dataclass
class AdditionalHeadersRef:
    """Object representing DNSPolicy additionalHeadersRef field"""

    name: str


@dataclass
class HealthCheck:  # pylint: disable=invalid-name,too-many-instance-attributes
    """Object representing DNSPolicy health check specification"""

    allowInsecureCertificates: Optional[bool] = None
    additionalHeadersRef: Optional[AdditionalHeadersRef] = None
    endpoint: Optional[str] = None
    expectedResponses: Optional[list[int]] = None
    failureThreshold: Optional[int] = None
    interval: Optional[str] = None
    port: Optional[int] = None
    protocol: Literal["http", "https"] = "https"


class DNSHealthCheckProbe(OpenShiftObject):
    """DNSHealthCheckProbe object"""

    def is_healthy(self) -> bool:
        """Returns True if DNSHealthCheckProbe endpoint is healthy"""
        return self.model.status.healthy


class DNSPolicy(OpenShiftObject):
    """DNSPolicy object"""

    @classmethod
    def create_instance(
        cls,
        openshift: OpenShiftClient,
        name: str,
        parent: Referencable,
        labels: dict[str, str] = None,
    ):
        """Creates new instance of DNSPolicy"""

        model: dict = {
            "apiVersion": "kuadrant.io/v1alpha1",
            "kind": "DNSPolicy",
            "metadata": {"name": name, "labels": labels},
            "spec": {"targetRef": parent.reference},
        }

        return cls(model, context=openshift.context)

    def set_health_check(self, health_check: HealthCheck):
        """Sets health check for DNSPolicy"""
        self.model["spec"]["healthCheck"] = asdict(health_check)

    def get_dns_health_probe(self) -> oc.APIObject:
        """Returns DNSHealthCheckProbe object for the created DNSPolicy"""
        with self.context:
            dns_probe = oc.selector("DNSHealthCheckProbe", labels={"kuadrant.io/dnspolicy": self.name()}).object()
        return DNSHealthCheckProbe(dns_probe.model, context=self.context)

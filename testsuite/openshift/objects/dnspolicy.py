"""Module for DNSPolicy related classes"""
from dataclasses import dataclass
from typing import Optional, Literal

import openshift as oc

from testsuite.objects import asdict
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects import OpenShiftObject
from testsuite.openshift.objects.gateway_api import Referencable


@dataclass
class HealthCheck:  # pylint: disable=invalid-name
    """Object representing DNSPolicy health check specification"""

    allowInsecureCertificates: Optional[bool] = None
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
        healthCheck: HealthCheck = None,
        labels: dict[str, str] = None,
    ):  # pylint: disable=invalid-name
        """Creates new instance of DNSPolicy"""

        model: dict = {
            "apiVersion": "kuadrant.io/v1alpha1",
            "kind": "DNSPolicy",
            "metadata": {"name": name, "labels": labels},
            "spec": {"targetRef": parent.reference},
        }

        if healthCheck:
            model["spec"]["healthCheck"] = asdict(healthCheck)

        return cls(model, context=openshift.context)

    def get_dns_health_probe(self) -> oc.APIObject:
        """Returns DNSHealthCheckProbe object for the created DNSPolicy"""
        dns_probe = oc.selector("DNSHealthCheckProbe", labels={"kuadrant.io/dnspolicy": self.name()}).object()
        return DNSHealthCheckProbe(dns_probe.model, context=self.context)

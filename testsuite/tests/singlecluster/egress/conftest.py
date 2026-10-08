"""Shared fixtures for all egress gateway tests.

Provides common egress infrastructure: Gateway, ServiceEntry, DestinationRule,
and ingress CA secret for TLS origination.

Prerequisites:
    - Authorino must trust the cluster CA for metadata.http calls to
      https://kubernetes.default.svc. See the Authorino CA trust patch in
      https://github.com/Kuadrant/architecture/issues/148#issuecomment-4133246181
"""

from dataclasses import dataclass
from typing import Optional

import backoff
import pytest

from testsuite.gateway import CustomReference, GatewayListener, URLRewriteFilter
from testsuite.gateway.exposers import StaticLocalHostname, LoadBalancerServiceExposer
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kubernetes.istio.destination_rule import DestinationRule
from testsuite.kubernetes.istio.service_entry import ServiceEntry
from testsuite.kubernetes.openshift.route import OpenshiftRoute
from testsuite.kubernetes.secret import Secret

pytestmark = [pytest.mark.kuadrant_only]

EGRESS_HOSTNAME = "httpbin.egress.local"
EXTERNAL_DOMAIN = "external.local"


@dataclass
class ExternalService:
    """Connection details of the service that the egress gateway treats as third-party.

    `address` is set only when the hostname has no DNS record and the ServiceEntry has to
    resolve it statically.
    """

    hostname: str
    port: int
    protocol: str
    address: Optional[str] = None

    @property
    def resolution(self) -> str:
        """Istio ServiceEntry resolution mode implied by the way the service is reachable"""
        return "STATIC" if self.address else "DNS"


@pytest.fixture(scope="module")
def external_service(request, exposer, backend, blame, cluster) -> ExternalService:
    """Backend presented to the mesh as an external service.

    On OpenShift it is exposed through a Route, which gives a DNS-resolvable TLS endpoint.
    On Kind the LoadBalancer IP has no DNS record, so the address is handed to the
    ServiceEntry for static resolution and the service is reached over plain HTTP.
    """
    if isinstance(exposer, LoadBalancerServiceExposer):
        address, _, port = backend.external_ip().rpartition(":")
        # Unique per module: a ServiceEntry host is namespace-wide, and Istio leaves the
        # behaviour undefined when several of them claim the same host. The OpenShift branch
        # below gets uniqueness for free from the blamed Route hostname.
        return ExternalService(f"{blame('ext')}.{EXTERNAL_DOMAIN}", int(port), "HTTP", address=address)

    route = OpenshiftRoute.create_instance(cluster, blame("backend"), backend.name, "http", tls=True)
    request.addfinalizer(route.delete)
    route.commit()
    return ExternalService(route.hostname, 443, "HTTPS")


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, module_label):
    """Egress Gateway with HTTP listener"""
    gw = KuadrantGateway.create_instance(cluster, blame("egress-gw"), {"app": module_label})
    gw.add_listener(GatewayListener(hostname="*.egress.local", name="egress"))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def service_entry(request, cluster, blame, external_service, module_label):
    """ServiceEntry registering the backend hostname as an external service"""
    entry = ServiceEntry.create_instance(
        cluster,
        blame("serent"),
        hosts=[external_service.hostname],
        ports=[
            {
                "number": external_service.port,
                "name": external_service.protocol.lower(),
                "protocol": external_service.protocol,
            }
        ],
        resolution=external_service.resolution,
        endpoints=[{"address": external_service.address}] if external_service.address else None,
        labels={"app": module_label},
    )
    request.addfinalizer(entry.delete)
    entry.commit()
    return entry


@pytest.fixture(scope="module")
def ingress_ca_secret(request, cluster, blame, external_service, module_label):
    """Secret containing the OpenShift ingress CA certificate, or None without TLS origination"""
    if external_service.protocol != "HTTPS":
        return None

    cert_data = cluster.change_project("openshift-ingress").get_secret("custom-cert")["tls.crt"]
    secret = Secret.create_instance(
        cluster, blame("ingress-ca"), stringData={"ca.crt": cert_data}, labels={"app": module_label}
    )
    request.addfinalizer(secret.delete)
    secret.commit()
    return secret


@pytest.fixture(scope="module")
def destination_rule(request, cluster, blame, external_service, ingress_ca_secret, module_label):
    """DestinationRule with TLS origination, or None when the external service speaks plain HTTP"""
    if ingress_ca_secret is None:
        return None

    rule = DestinationRule.create_instance(
        cluster,
        blame("desrul"),
        host=external_service.hostname,
        tls_mode="SIMPLE",
        sni=external_service.hostname,
        credential_name=ingress_ca_secret.name(),
        labels={"app": module_label},
    )
    request.addfinalizer(rule.delete)
    rule.commit()
    return rule


@pytest.fixture(scope="module")
def external_reference(external_service):
    """backendRef addressing the external service from an egress HTTPRoute"""
    return CustomReference(
        group="networking.istio.io",
        kind="Hostname",
        name=external_service.hostname,
        port=external_service.port,
    )


@pytest.fixture(scope="module")
def route(
    request,
    gateway,
    cluster,
    blame,
    external_service,
    external_reference,
    module_label,
    service_entry,
    destination_rule,
):
    """HTTPRoute routing egress traffic through the gateway to the external service"""
    # pylint: disable=unused-argument
    route = HTTPRoute.create_instance(cluster, blame("route"), gateway, {"app": module_label})
    route.add_hostname(EGRESS_HOSTNAME)
    route.add_rule(external_reference, filters=[URLRewriteFilter(hostname=external_service.hostname)])
    request.addfinalizer(route.delete)
    route.commit()
    route.wait_for_ready()
    return route


@pytest.fixture(scope="module")
def client(gateway, route):  # pylint: disable=unused-argument
    """HTTPX client sending requests to the egress gateway"""
    client = StaticLocalHostname(EGRESS_HOSTNAME, gateway.external_ip).client()

    # A Gateway reports Programmed before Envoy is actually serving its routes, so the first
    # requests through a freshly created egress gateway fail with a 503 or a connection error.
    # KuadrantClient retries 503 on its own, but only for about half a minute, which a cold
    # gateway can outlast. Absorb the cold start once here instead of in every test.
    @backoff.on_predicate(backoff.constant, lambda serving: not serving, interval=3, max_tries=20, jitter=None)
    def gateway_serving():
        result = client.get("/")
        return result.error is None and result.status_code != 503

    assert gateway_serving(), "Egress gateway did not start serving traffic"

    yield client
    client.close()

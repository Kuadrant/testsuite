"""Shared fixtures for all egress gateway tests.

Provides common egress infrastructure: Gateway, ServiceEntry, DestinationRule,
and ingress CA secret for TLS origination.

Prerequisites:
    - Authorino must trust the cluster CA for metadata.http calls to
      https://kubernetes.default.svc. See the Authorino CA trust patch in
      https://github.com/Kuadrant/architecture/issues/148#issuecomment-4133246181
"""

import pytest

from testsuite.gateway import Hostname, GatewayListener
from testsuite.gateway.exposers import StaticLocalHostname, LoadBalancerServiceExposer
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.kubernetes.istio.destination_rule import DestinationRule
from testsuite.kubernetes.istio.service_entry import ServiceEntry
from testsuite.kubernetes.openshift.route import OpenshiftRoute
from testsuite.kubernetes.secret import Secret

pytestmark = [pytest.mark.kuadrant_only]

EGRESS_HOSTNAME = "httpbin.egress.local"


@pytest.fixture(scope="module")
def hostname(request, exposer, backend, blame, cluster) -> Hostname:
    """Expose the backend service directly via an OpenShift Route"""
    if isinstance(exposer, LoadBalancerServiceExposer):
        pytest.skip("Egress tests use OpenShift Route for backend exposure, hence are not available on Kind cluster")

    route = OpenshiftRoute.create_instance(cluster, blame("backend"), backend.name, "http", tls=True)
    request.addfinalizer(route.delete)
    route.commit()
    return route


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
def service_entry(request, cluster, blame, hostname, module_label):
    """ServiceEntry registering the backend routable hostname as an external service"""
    entry = ServiceEntry.create_instance(
        cluster,
        blame("serent"),
        hosts=[hostname.hostname],
        ports=[{"number": 443, "name": "https", "protocol": "HTTPS"}],
        labels={"app": module_label},
    )
    request.addfinalizer(entry.delete)
    entry.commit()
    return entry


@pytest.fixture(scope="module")
def ingress_ca_secret(request, cluster, blame, module_label):
    """Secret containing the OpenShift ingress CA certificate for TLS origination"""
    cert_data = cluster.change_project("openshift-ingress").get_secret("custom-cert")["tls.crt"]
    secret = Secret.create_instance(
        cluster, blame("ingress-ca"), stringData={"ca.crt": cert_data}, labels={"app": module_label}
    )
    request.addfinalizer(secret.delete)
    secret.commit()
    return secret


@pytest.fixture(scope="module")
def destination_rule(request, cluster, blame, hostname, ingress_ca_secret, module_label):
    """DestinationRule with TLS origination for the backend"""
    rule = DestinationRule.create_instance(
        cluster,
        blame("desrul"),
        host=hostname.hostname,
        tls_mode="SIMPLE",
        sni=hostname.hostname,
        credential_name=ingress_ca_secret.name(),
        labels={"app": module_label},
    )
    request.addfinalizer(rule.delete)
    rule.commit()
    return rule


@pytest.fixture(scope="module")
def client(gateway, route):  # pylint: disable=unused-argument
    """HTTPX client sending requests to the egress gateway"""
    client = StaticLocalHostname(EGRESS_HOSTNAME, gateway.external_ip).client()
    yield client
    client.close()

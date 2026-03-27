"""Tests for AuthPolicy and RateLimitPolicy with egress gateway.

Based on https://github.com/Kuadrant/architecture/issues/147#issuecomment-4053003829
Sets up an egress gateway with Istio's ServiceEntry, DestinationRule,
and HTTPRoute with URLRewrite filter to route egress traffic to an externally deployed service.
Validates that AuthPolicy and RateLimitPolicy are enforced on egress traffic.
"""

from time import sleep
import pytest

from testsuite.gateway import Hostname, GatewayListener, CustomReference, URLRewriteFilter
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.gateway.exposers import LoadBalancerServiceExposer, StaticLocalHostname
from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.kubernetes.istio.destination_rule import DestinationRule
from testsuite.kubernetes.istio.service_entry import ServiceEntry
from testsuite.kubernetes.openshift.route import OpenshiftRoute
from testsuite.kubernetes.secret import Secret

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.egress_gateway]

EGRESS_HOSTNAME = "httpbin.egress.local"
LIMIT = Limit(3, "5s")


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
    service_entry = ServiceEntry.create_instance(
        cluster,
        blame("serent"),
        hosts=[hostname.hostname],
        ports=[{"number": 443, "name": "https", "protocol": "HTTPS"}],
        labels={"app": module_label},
    )
    request.addfinalizer(service_entry.delete)
    service_entry.commit()
    return service_entry


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
    destination_rule = DestinationRule.create_instance(
        cluster,
        blame("desrul"),
        host=hostname.hostname,
        tls_mode="SIMPLE",
        sni=hostname.hostname,
        credential_name=ingress_ca_secret.name(),
        labels={"app": module_label},
    )
    request.addfinalizer(destination_rule.delete)
    destination_rule.commit()
    return destination_rule


@pytest.fixture(scope="module")
def route(request, gateway, cluster, blame, hostname, module_label, service_entry, destination_rule):
    """HTTPRoute routing egress traffic through the gateway to the backend via Hostname backendRef"""
    # pylint: disable=unused-argument
    route = HTTPRoute.create_instance(cluster, blame("route"), gateway, {"app": module_label})
    route.add_hostname(EGRESS_HOSTNAME)
    route.add_rule(
        CustomReference(group="networking.istio.io", kind="Hostname", name=hostname.hostname, port=443),
        filters=[URLRewriteFilter(hostname=hostname.hostname)],
    )
    request.addfinalizer(route.delete)
    route.commit()
    route.wait_for_ready()
    return route


@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider):
    """Add OIDC identity to AuthPolicy for egress"""
    authorization.identity.add_oidc("oidc", oidc_provider.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add rate limit to RateLimitPolicy for egress"""
    rate_limit.add_limit("3_5s", [LIMIT])
    return rate_limit


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns OIDC authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def client(gateway, route):  # pylint: disable=unused-argument
    """HTTPX client sending requests to the egress gateway with the correct Host header"""
    client = StaticLocalHostname(EGRESS_HOSTNAME, gateway.external_ip).client()
    yield client
    client.close()


def test_egress_authorization(client, auth):
    """Test that AuthPolicy is enforced on egress gateway traffic"""
    assert client.get("/get").status_code == 401

    response = client.get("/get", auth=auth)
    assert response.status_code == 200


def test_egress_ratelimit(client, auth):
    """Test that RateLimitPolicy is enforced on egress gateway traffic"""
    sleep(5 + 1)  # make sure request limit quota is reset before starting the test

    responses = client.get_many("/get", LIMIT.limit, auth=auth)
    responses.assert_all(status_code=200)

    assert client.get("/get", auth=auth).status_code == 429

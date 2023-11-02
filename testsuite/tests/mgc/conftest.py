"""Conftest for MGC tests"""
import pytest
from openshift import selector
from weakget import weakget

from testsuite.openshift.httpbin import Httpbin
from testsuite.openshift.objects.dnspolicy import DNSPolicy
from testsuite.openshift.objects.gateway_api import CustomReference
from testsuite.openshift.objects.gateway_api.gateway import MGCGateway, GatewayProxy
from testsuite.openshift.objects.gateway_api.route import HTTPRoute
from testsuite.openshift.objects.proxy import Proxy
from testsuite.openshift.objects.route import Route
from testsuite.openshift.objects.tlspolicy import TLSPolicy


@pytest.fixture(scope="module")
def backend(request, gateway, blame, label):
    """Deploys Httpbin backend"""
    httpbin = Httpbin(gateway.openshift, blame("httpbin"), label)
    request.addfinalizer(httpbin.delete)
    httpbin.commit()
    return httpbin


@pytest.fixture(scope="session")
def spokes(testconfig):
    """Returns Map of spokes names and their respective clients"""
    spokes = weakget(testconfig)["mgc"]["spokes"] % {}
    assert len(spokes) > 0, "No spokes configured"
    return spokes


@pytest.fixture(scope="module")
def upstream_gateway(request, openshift, blame, hostname, module_label):
    """Creates and returns configured and ready upstream Gateway"""
    upstream_gateway = MGCGateway.create_instance(
        openshift=openshift,
        name=blame("mgc-gateway"),
        gateway_class="kuadrant-multi-cluster-gateway-instance-per-cluster",
        hostname=f"*.{hostname}",
        tls=True,
        placement="http-gateway",
        labels={"app": module_label},
    )
    request.addfinalizer(upstream_gateway.delete_tls_secret)  # pylint: disable=no-member
    request.addfinalizer(upstream_gateway.delete)
    upstream_gateway.commit()
    # we cannot wait here because of referencing not yet existent tls secret which would be provided later by tlspolicy
    # upstream_gateway.wait_for_ready()

    return upstream_gateway


@pytest.fixture(scope="module")
def proxy(request, gateway, backend, module_label) -> Proxy:
    """Deploys Envoy that wire up the Backend behind the reverse-proxy and Authorino instance"""
    envoy: Proxy = GatewayProxy(gateway, module_label, backend)
    request.addfinalizer(envoy.delete)
    envoy.commit()
    return envoy


@pytest.fixture(scope="module")
def initial_host(hostname):
    """Hostname that will be added to HTTPRoute"""
    return f"route.{hostname}"


@pytest.fixture(scope="session")
def self_signed_cluster_issuer():
    """Reference to cluster self-signed certificate issuer"""
    return CustomReference(
        group="cert-manager.io",
        kind="ClusterIssuer",
        name="selfsigned-cluster-issuer",
    )


@pytest.fixture(scope="module")
def route(request, proxy, blame, gateway, initial_host, backend) -> Route:
    """Exposed Route object"""
    route = HTTPRoute.create_instance(
        gateway.openshift,
        blame("route"),
        gateway,
        initial_host,
        backend,
        labels={"app": proxy.label},
    )
    request.addfinalizer(route.delete)
    route.commit()
    return route


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def gateway(upstream_gateway, spokes, hub_policies_commit):
    """Downstream gateway, e.g. gateway on a spoke cluster"""
    # wait for upstream gateway here to be able to get spoke gateways
    upstream_gateway.wait_for_ready()
    gw = upstream_gateway.get_spoke_gateway(spokes)
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module", params=["aws-mz", "gcp-mz"])
def base_domain(request, openshift):
    """Returns preconfigured base domain"""
    mz_name = request.param

    with openshift.context:
        zone = selector(f"managedzone/{mz_name}").object()
    return zone.model["spec"]["domainName"]


@pytest.fixture(scope="module")
def hostname(blame, base_domain):
    """Returns domain used for testing"""
    return f"{blame('mgc')}.{base_domain}"


@pytest.fixture(scope="module")
def dns_policy(blame, upstream_gateway, module_label):
    """DNSPolicy fixture"""
    policy = DNSPolicy.create_instance(
        upstream_gateway.openshift, blame("dns"), upstream_gateway, labels={"app": module_label}
    )
    return policy


@pytest.fixture(scope="module")
def tls_policy(blame, upstream_gateway, module_label, self_signed_cluster_issuer):
    """TLSPolicy fixture"""
    policy = TLSPolicy.create_instance(
        upstream_gateway.openshift,
        blame("tls"),
        parent=upstream_gateway,
        issuer=self_signed_cluster_issuer,
        labels={"app": module_label},
    )
    return policy


@pytest.fixture(scope="module")
def hub_policies_commit(request, upstream_gateway, dns_policy, tls_policy):
    """Commits all important stuff before tests"""
    for component in [dns_policy, tls_policy]:
        if component is not None:
            request.addfinalizer(component.delete)
            component.commit()

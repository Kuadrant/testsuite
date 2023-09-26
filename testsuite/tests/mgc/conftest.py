"""Conftest for MGC tests"""
import pytest
from openshift import selector
from weakget import weakget

from testsuite.openshift.httpbin import Httpbin
from testsuite.openshift.objects.dnspolicy import DNSPolicy
from testsuite.openshift.objects.gateway_api.gateway import MGCGateway, GatewayProxy
from testsuite.openshift.objects.gateway_api.route import HTTPRoute
from testsuite.openshift.objects.proxy import Proxy
from testsuite.openshift.objects.route import Route


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
def upstream_gateway(request, openshift, blame, hostname, module_label, testconfig):
    """Creates and returns configured and ready upstream Gateway"""
    upstream_gateway = MGCGateway.create_instance(
        openshift=openshift,
        name=blame("mgc-gateway"),
        gateway_class="kuadrant-multi-cluster-gateway-instance-per-cluster",
        hostname=f"*.{hostname}",
        placement="http-gateway",
        kuadrant_namespace=testconfig["kuadrant"]["project"],
        labels={"app": module_label},
    )
    request.addfinalizer(upstream_gateway.delete)
    upstream_gateway.commit()
    upstream_gateway.wait_for_ready()

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


@pytest.fixture(scope="module")
def gateway(upstream_gateway, spokes):
    """Downstream gateway, e.g. gateway on a spoke cluster"""
    gw = upstream_gateway.get_spoke_gateway(spokes)
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def base_domain(openshift):
    """Returns preconfigured base domain"""
    with openshift.context:
        zone = selector("managedzone/mgc-dev-mz").object()
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


@pytest.fixture(scope="module", autouse=True)
def commit(request, dns_policy):
    """Commits all important stuff before tests"""
    for component in [dns_policy]:
        if component is not None:
            request.addfinalizer(component.delete)
            component.commit()

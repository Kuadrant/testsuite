"""
This module contains the very basic tests and their dependencies for MGC

Prerequisites:
* the hub cluster is also a spoke cluster so that everything happens on the only cluster
* multi-cluster-gateways ns is created and set as openshift["project"]
* managedclustersetbinding is created in openshift["project"]
* placement named "local-cluster" is created in openshift["project"] and bound to clusterset
* gateway class "kuadrant-multi-cluster-gateway-instance-per-cluster" is created
* openshift2["project"] is set

Notes:
* dnspolicies are created and bound to gateways automatically by mgc operator
* dnspolicies leak at this moment
"""
from time import sleep
import httpx
import pytest
from testsuite.openshift.httpbin import Httpbin
from testsuite.openshift.objects.gateway_api import MGCGateway, HTTPRoute

pytestmark = [pytest.mark.mgc]


@pytest.fixture(scope="module")
def base_domain(openshift):
    """Returns preconfigured base domain"""
    managed_zone = openshift.do_action("get", ["managedzone", "mgc-dev-mz", "-o", "yaml"], parse_output=True)
    return managed_zone.model["spec"]["domainName"]


@pytest.fixture(scope="module")
def hostname(blame, base_domain):
    """Returns domain used for testing"""
    return f"{blame('mgc')}.{base_domain}"


@pytest.fixture(scope="module")
def gateway(request, openshift, blame, hostname):
    """Creates and returns configured and ready upstream Gateway"""
    upstream_gateway = MGCGateway.create_instance(
        openshift=openshift,
        name=blame("mgc-gateway"),
        gateway_class_name="kuadrant-multi-cluster-gateway-instance-per-cluster",
        hostname=hostname,
        placement="local-gateway",
    )
    upstream_gateway.commit()
    request.addfinalizer(upstream_gateway.delete)
    upstream_gateway.wait_for_ready()

    return upstream_gateway


def _downstream_gateway_of_gateway(gateway, openshift):
    """
    Upon upstream Gateway creation MGC creates downstream Gateways on spoke clusters according to the Placement decision
    HTTPRoutes must be created on the spoke clusters binding to the corresponding downstream Gateway
    """
    # in future this function may be a method of MGCGateway if done properly
    openshift = openshift.change_project(f"kuadrant-{gateway.namespace()}")
    downstream_gateway = openshift.do_action("get", ["gateway", gateway.name(), "-o", "yaml"], parse_output=False)
    downstream_gateway = MGCGateway(string_to_model=downstream_gateway.out(), context=openshift.context)
    # should be deleted automatically by the mgc operator upon mgc gateway deletion
    return downstream_gateway


@pytest.fixture(scope="module")
def backend(request, openshift2, blame, label):
    """Deploys Httpbin backend"""
    httpbin = Httpbin(openshift2, blame("httpbin"), label)
    request.addfinalizer(httpbin.delete)
    httpbin.commit()
    return httpbin


@pytest.fixture(scope="module")
def http_route(gateway, backend, blame, openshift2):
    """Creates and returns HTTPRoute bound to the backend and the downstream Gateway"""
    downstream_gateway = _downstream_gateway_of_gateway(gateway, openshift2)

    route = HTTPRoute.create_instance(
        openshift2,
        blame("route"),
        parent=downstream_gateway,
        hostname=downstream_gateway.hostname,
        backend=backend,
    )

    route.commit()
    yield route
    route.delete()


def test_gateway_readiness(gateway):
    """Tests whether the Gateway was successfully placed by having its IP address assigned"""
    assert gateway.is_ready()


def test_smoke(http_route):
    """
    Tests whether the backend, exposed using the HTTPRoute and Gateway, was exposed correctly,
    having a tls secured endpoint with a hostname managed by MGC
    """
    backend_hostname = http_route.hostnames[0]
    backend_client = httpx.Client(verify=False)  # self-signed certificate; TBD

    sleep(30)  # wait for DNS record to propagate correctly; TBD

    response = backend_client.get(f"https://{backend_hostname}/get")
    assert response.status_code == 200

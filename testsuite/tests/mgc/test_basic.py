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

import pytest

from testsuite.openshift.objects.gateway_api.gateway import MGCGateway

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
def gateway(request, openshift, blame, hostname, module_label):
    """Creates and returns configured and ready upstream Gateway"""
    upstream_gateway = MGCGateway.create_instance(
        openshift=openshift,
        name=blame("mgc-gateway"),
        gateway_class="kuadrant-multi-cluster-gateway-instance-per-cluster",
        hostname=hostname,
        placement="local-gateway",
        labels={"app": module_label},
    )
    request.addfinalizer(upstream_gateway.delete)
    upstream_gateway.commit()
    upstream_gateway.wait_for_ready()

    openshift = openshift.change_project(f"kuadrant-{upstream_gateway.namespace()}")
    downstream_gateway = openshift.do_action(
        "get", ["gateway", upstream_gateway.name(), "-o", "yaml"], parse_output=False
    )
    downstream_gateway = MGCGateway(string_to_model=downstream_gateway.out(), context=openshift.context)
    return downstream_gateway


def test_gateway_readiness(gateway):
    """Tests whether the Gateway was successfully placed by having its IP address assigned"""
    assert gateway.is_ready()


def test_smoke(route):
    """
    Tests whether the backend, exposed using the HTTPRoute and Gateway, was exposed correctly,
    having a tls secured endpoint with a hostname managed by MGC
    """
    backend_client = route.client(verify=False)  # self-signed certificate; TBD

    sleep(30)  # wait for DNS record to propagate correctly; TBD

    response = backend_client.get("get")
    assert response.status_code == 200

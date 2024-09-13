"""Create 2 gateways with 64 listeners each and confirm they are reachable with DNSPolicy applied"""

import pytest

from testsuite.httpx import KuadrantClient
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.kuadrant.policy.dns import DNSPolicy

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy]

MAX_GATEWAY_LISTENERS = 64


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, base_domain, module_label):
    """Create first gateway with 64 listeners"""
    gw = KuadrantGateway.create_instance(cluster, blame("gw"), f"gw1-api.{base_domain}", {"app": module_label})
    for i in range(1, MAX_GATEWAY_LISTENERS):
        gw.add_listener(f"api{i}", f"gw1-api{i}.{base_domain}")
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def gateway2(request, cluster, blame, base_domain, module_label):
    """Create second gateway with 64 listeners"""
    gw = KuadrantGateway.create_instance(cluster, blame("gw"), f"gw2-api.{base_domain}", {"app": module_label})
    for i in range(1, MAX_GATEWAY_LISTENERS):
        gw.add_listener(f"api{i}", f"gw2-api{i}.{base_domain}")
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def dns_policy2(blame, gateway2, module_label, dns_provider_secret):
    """Create DNSPolicy for second gateway"""
    return DNSPolicy.create_instance(
        gateway2.cluster, blame("dns"), gateway2, dns_provider_secret, labels={"app": module_label}
    )


@pytest.fixture(scope="module")
def routes(request, gateway, gateway2, blame, wildcard_domain, backend, module_label):
    """Create routes for both gateways"""
    for g in [gateway, gateway2]:
        route = HTTPRoute.create_instance(g.cluster, blame("route"), g, {"app": module_label})
        route.add_hostname(wildcard_domain)
        route.add_backend(backend)
        request.addfinalizer(route.delete)
        route.commit()


@pytest.fixture(scope="module", autouse=True)
def commit(request, routes, dns_policy, dns_policy2):  # pylint: disable=unused-argument
    """Commit and wait for DNSPolicies to be fully enforced"""
    for component in [dns_policy, dns_policy2]:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()


def test_gateway_max_listeners(gateway, gateway2, dns_policy, dns_policy2, base_domain):
    """Verify that both gateways are affected by DNSPolicy and their listeners are reachable"""
    assert gateway.refresh().is_affected_by(dns_policy)
    assert gateway2.refresh().is_affected_by(dns_policy2)

    assert KuadrantClient(base_url=f"http://gw1-api.{base_domain}").get("/get").response.status_code == 200
    assert KuadrantClient(base_url=f"http://gw1-api63.{base_domain}").get("/get").response.status_code == 200

    assert KuadrantClient(base_url=f"http://gw2-api21.{base_domain}").get("/get").response.status_code == 200
    assert KuadrantClient(base_url=f"http://gw2-api53.{base_domain}").get("/get").response.status_code == 200

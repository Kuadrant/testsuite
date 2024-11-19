"""Tests for DNSPolicy health checks with HTTP only endpoint - healthy endpoint"""

import pytest

from testsuite.gateway import GatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.kuadrant.policy.dns import HealthCheck

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy]


@pytest.fixture(scope="module")
def health_check():
    """Returns healthy endpoint specification for DNSPolicy health check"""
    return HealthCheck(
        path="/get",
        interval="5s",
        protocol="HTTP",
        port=80,
    )


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, base_domain, module_label, subdomain):
    """Create gateway without TLS enabled"""
    gw = KuadrantGateway.create_instance(cluster, blame("gw"), {"app": module_label})
    gw.add_listener(GatewayListener(hostname=f"{subdomain}.{base_domain}"))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, dns_policy):  # pylint: disable=unused-argument
    """Commits dnspolicy only"""
    request.addfinalizer(dns_policy.delete)
    dns_policy.commit()
    dns_policy.wait_for_ready()


def test_healthy_endpoint_http(dns_health_probe, client):
    """Test healthy endpoint check without TLS enabled"""
    assert dns_health_probe.is_healthy()

    response = client.get("/get")
    assert response.status_code == 200

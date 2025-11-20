"""Test that Gateway will behave properly after attached DNSPolicy is deleted"""

from time import sleep

import pytest

from testsuite.gateway.gateway_api.gateway import KuadrantGateway, GatewayListener

pytestmark = [pytest.mark.dnspolicy]


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, wildcard_domain, module_label):
    """Create gateway without TLS enabled"""
    gw = KuadrantGateway.create_instance(cluster, blame("gw"), {"app": module_label})
    gw.add_listener(GatewayListener(hostname=wildcard_domain))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, dns_policy):  # pylint: disable=unused-argument
    """Commits dnspolicy"""
    request.addfinalizer(dns_policy.delete)
    dns_policy.commit()
    dns_policy.wait_for_ready()


def test_dnspolicy_removal(gateway, dns_policy, client):
    """
    Test that Gateway will behave properly after attached DNSPolicy is deleted
    - Verify that Gateway is affected by DNSPolicy and requests are successful
    - Delete attached DNSPolicy
    - Verify that Gateway is no longer affected by DNSPolicy and requests are failing
    """
    assert gateway.refresh().is_affected_by(dns_policy)
    response = client.get("/get")
    assert response.status_code == 200

    dns_ttl = gateway.get_listener_dns_ttl(GatewayListener.name)
    dns_policy.delete()
    # wait for records deletion/ttl expiration from the previous request
    sleep(dns_ttl)

    assert not gateway.refresh().is_affected_by(dns_policy)
    response = client.get("/get")
    assert response.has_dns_error()

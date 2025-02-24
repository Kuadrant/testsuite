"""
Test for changing targetRef field in DNSPolicy & TLSPolicy
"""

import pytest

from testsuite.gateway import TLSGatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy, pytest.mark.tlspolicy]


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, wildcard_domain, module_label):
    """Create Gateway 1 with TLSGatewayListener"""
    gateway_name = blame("gw")
    gw = KuadrantGateway.create_instance(
        cluster,
        gateway_name,
        {"app": module_label},
    )
    gw.add_listener(TLSGatewayListener(hostname=wildcard_domain, gateway_name=gateway_name))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def gateway2(request, cluster, blame, wildcard_domain2, module_label):
    """Create Gateway 2 with TLSGatewayListener"""
    gateway_name = blame("gw2")
    gw = KuadrantGateway.create_instance(
        cluster,
        gateway_name,
        {"app": module_label},
    )
    gw.add_listener(TLSGatewayListener(hostname=wildcard_domain2, gateway_name=gateway_name))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


def test_update_policies_target_ref(
    route2, tls_policy, gateway, gateway2, client, dns_policy, change_target_ref, hostname2
):  # pylint: disable=unused-argument
    """Test updating the targetRef of both TLSPolicy and DNSPolicy from Gateway 1 to Gateway 2"""
    assert gateway.wait_until(lambda obj: obj.is_affected_by(tls_policy))
    assert gateway.wait_until(lambda obj: obj.is_affected_by(dns_policy))
    assert gateway2.wait_until(lambda obj: not obj.is_affected_by(tls_policy))
    assert gateway2.wait_until(lambda obj: not obj.is_affected_by(dns_policy))

    response = client.get("/get")
    assert not response.has_cert_verify_error()
    assert not response.has_dns_error()
    assert response.status_code == 200

    change_target_ref(tls_policy, gateway2)
    change_target_ref(dns_policy, gateway2)

    assert gateway.wait_until(lambda obj: not obj.is_affected_by(tls_policy))
    assert gateway.wait_until(lambda obj: not obj.is_affected_by(dns_policy))
    assert gateway2.wait_until(lambda obj: obj.is_affected_by(tls_policy))
    assert gateway2.wait_until(lambda obj: obj.is_affected_by(dns_policy))

    client2 = hostname2.client()

    response = client2.get("/get")
    assert not response.has_cert_verify_error()
    assert not response.has_dns_error()
    assert response.status_code == 200

    client2.close()

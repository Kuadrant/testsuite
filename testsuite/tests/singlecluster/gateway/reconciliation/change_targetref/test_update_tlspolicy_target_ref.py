"""
Test for changing targetRef field in TLSPolicy
"""

import time

import pytest

from testsuite.gateway import TLSGatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.hostname import StaticHostname
from testsuite.httpx import KuadrantClient

pytestmark = [pytest.mark.dnspolicy, pytest.mark.tlspolicy]


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


@pytest.fixture(scope="module")
def custom_client():
    """
    Provides a client for both gateway's to avoid secret and cert errors
    """

    def _client_new(hostname: str, gateway_instance: KuadrantGateway):
        return StaticHostname(hostname, gateway_instance.get_tls_cert).client()

    return _client_new


def test_update_tls_policy_target_ref(
    tls_policy, gateway, gateway2, dns_policy, dns_policy2, change_target_ref, custom_client, hostname, hostname2
):  # pylint: disable=unused-argument
    """Test updating the targetRef of TLSPolicy from Gateway 1 to Gateway 2"""
    assert gateway.wait_until(lambda obj: obj.is_affected_by(tls_policy))
    assert gateway2.wait_until(lambda obj: not obj.is_affected_by(tls_policy))

    response = custom_client(hostname.hostname, gateway).get("/get")
    assert not response.has_cert_verify_error()
    assert response.status_code == 200

    response = KuadrantClient(base_url=f"https://{hostname2.hostname}", verify=False).get("/get")
    assert response.has_tls_error()

    change_target_ref(tls_policy, gateway2)

    assert gateway.wait_until(lambda obj: not obj.is_affected_by(tls_policy))
    assert gateway2.wait_until(lambda obj: obj.is_affected_by(tls_policy))

    response = custom_client(hostname2.hostname, gateway2).get("/get")
    assert not response.has_cert_verify_error()
    assert response.status_code == 200

    # Delete TLS secret to verify gateway1 no longer serves valid TLS traffic
    tls_secret = gateway.get_tls_secret(hostname.hostname)
    tls_secret.delete()
    time.sleep(10)  # Allow extra time for secret deletion to propagate

    response = KuadrantClient(base_url=f"https://{hostname.hostname}", verify=False).get("/get")
    assert response.has_tls_error()

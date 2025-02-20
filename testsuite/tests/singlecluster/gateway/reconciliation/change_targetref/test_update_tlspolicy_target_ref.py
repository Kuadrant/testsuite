"""
Test for changing targetRef field in TLSPolicy
"""

import pytest

from testsuite.gateway import TLSGatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.httpx import KuadrantClient
from testsuite.kuadrant.policy.tls import TLSPolicy

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


@pytest.fixture(scope="module")
def tls_policy2(request, blame, gateway2, module_label, cluster_issuer):
    """Creates a second TLSPolicy to prevent TLS secret errors from interfering with test execution"""
    policy = TLSPolicy.create_instance(
        gateway2.cluster,
        blame("tls2"),
        parent=gateway2,
        issuer=cluster_issuer,
        labels={"app": module_label},
    )
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()
    return policy


def test_update_tls_policy_target_ref(
    route2, tls_policy, tls_policy2, gateway, gateway2, client, client2, dns_policy, dns_policy2, change_target_ref
):  # pylint: disable=unused-argument
    """Test updating the targetRef of TLSPolicy from Gateway 1 to Gateway 2"""
    tls_policy2.delete()  # Delete tls_policy2 as it was only used to prevent initial TLS secret errors

    gateway.refresh()
    assert gateway.is_affected_by(tls_policy)

    response = client.get("/get")
    assert not response.has_cert_verify_error()
    assert response.status_code == 200

    response = KuadrantClient(base_url=str(client2.base_url), verify=True).get("/get")
    assert response.has_cert_verify_error()

    change_target_ref(tls_policy, gateway2)

    gateway2.refresh()
    assert gateway2.is_affected_by(tls_policy)

    response = client2.get("/get")
    assert not response.has_cert_verify_error()
    assert response.status_code == 200

    response = KuadrantClient(base_url=str(client.base_url), verify=True).get("/get")
    assert response.has_cert_verify_error()

"""
Test for changing targetRef field in DNSPolicy
"""

from time import sleep
import pytest

from testsuite.gateway import GatewayListener

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy]


def test_update_dns_policy_target_ref(
    gateway, gateway2, client, client2, dns_policy, change_target_ref
):  # pylint: disable=unused-argument
    """Test updating the targetRef of DNSPolicy from Gateway 1 to Gateway 2"""
    assert gateway.wait_until(lambda obj: obj.is_affected_by(dns_policy))
    assert gateway2.wait_until(lambda obj: not obj.is_affected_by(dns_policy))

    response = client.get("/get")
    assert not response.has_dns_error()
    assert response.status_code == 200

    response = client2.get("/get")
    assert response.has_dns_error()

    dns_ttl = gateway.get_listener_dns_ttl(GatewayListener.name)

    change_target_ref(dns_policy, gateway2)

    # Wait for records deletion/ttl expiration from the previous request
    sleep(dns_ttl)

    assert gateway.wait_until(lambda obj: not obj.is_affected_by(dns_policy))
    assert gateway2.wait_until(lambda obj: obj.is_affected_by(dns_policy))

    response = client2.get("/get")
    assert not response.has_dns_error()
    assert response.status_code == 200

    response = client.get("/get")
    assert response.has_dns_error()

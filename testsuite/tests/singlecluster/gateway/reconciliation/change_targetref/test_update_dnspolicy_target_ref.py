"""
Test for changing targetRef field in DNSPolicy
"""

from time import sleep
import pytest

from testsuite.gateway import GatewayListener

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy]


@pytest.fixture(scope="module")
def client(route, hostname):  # pylint: disable=unused-argument
    """Returns httpx client to be used for requests"""
    client = hostname.client()
    yield client
    client.close()


@pytest.fixture(scope="module")
def client2(route2, hostname2):  # pylint: disable=unused-argument
    """Returns httpx client for Gateway 2"""
    client = hostname2.client()
    yield client
    client.close()


def test_update_dns_policy_target_ref(
    gateway, gateway2, client, client2, dns_policy, change_target_ref
):  # pylint: disable=unused-argument
    """Test updating the targetRef of DNSPolicy from Gateway 1 to Gateway 2"""
    assert gateway.refresh().is_affected_by(dns_policy)
    assert not gateway2.refresh().is_affected_by(dns_policy)

    response = client.get("/get")
    assert not response.has_dns_error()
    assert response.status_code == 200

    response = client2.get("/get")
    assert response.has_dns_error()

    dns_ttl = gateway.get_listener_dns_ttl(GatewayListener.name)

    change_target_ref(dns_policy, gateway2)

    # Wait for records deletion/ttl expiration from the previous request
    sleep(dns_ttl)

    assert not gateway.refresh().is_affected_by(dns_policy)
    assert gateway2.refresh().is_affected_by(dns_policy)

    response = client2.get("/get")
    assert not response.has_dns_error()
    assert response.status_code == 200

    response = client.get("/get")
    assert response.has_dns_error()

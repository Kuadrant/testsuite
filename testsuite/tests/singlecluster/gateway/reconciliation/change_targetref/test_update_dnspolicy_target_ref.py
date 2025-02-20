"""
Test for changing targetRef field in DNSPolicy
"""

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy, pytest.mark.tlspolicy]


@pytest.fixture(scope="module")
def route2():
    """
    Override the route 2 fixture
    """
    return None


@pytest.fixture(scope="module")
def client2(route, hostname2):  # pylint: disable=unused-argument
    """Returns httpx client for Gateway 2"""
    client = hostname2.client()
    yield client
    client.close()


def test_update_dns_policy_target_ref(
    route,
    gateway,
    gateway2,
    client,
    client2,
    dns_policy,
    change_target_ref,
    change_route_parent_ref,
    hostname2,
    hostname,
):  # pylint: disable=unused-argument
    """Test updating the targetRef of DNSPolicy from Gateway 1 to Gateway 2"""
    assert gateway.wait_until(lambda obj: obj.is_affected_by(dns_policy))
    assert gateway2.wait_until(lambda obj: not obj.is_affected_by(dns_policy))

    response = client.get("/get")
    assert not response.has_dns_error()
    assert response.status_code == 200

    response = client2.get("/get")
    assert response.has_dns_error()

    change_target_ref(dns_policy, gateway2)
    change_route_parent_ref(route, gateway2, hostname2.hostname)

    assert gateway.wait_until(lambda obj: not obj.is_affected_by(dns_policy))
    assert gateway2.wait_until(lambda obj: obj.is_affected_by(dns_policy))

    response = client2.get("/get")
    assert not response.has_dns_error()
    assert response.status_code == 200

    response = client.get("/get")
    assert response.has_dns_error()

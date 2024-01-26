"""Tests that HTTPRoute spec.hostnames changes are reconciled when changed."""

import pytest


@pytest.fixture
def second_hostname(exposer, gateway, blame):
    """Add a second hostname to a HTTPRoute"""
    return exposer.expose_hostname(blame("second"), gateway)


@pytest.fixture
def client2(second_hostname):
    """Client for a second hostname to HTTPRoute"""
    client = second_hostname.client()
    yield client
    client.close()


def test_add_host(client, client2, second_hostname, route, resilient_request):
    """
    Tests that HTTPRoute spec.hostnames changes are reconciled when changed:
      * Test that both hostnames work
      * Remove second hostname
      * Test that second hostname doesn't work
      * Add back second hostname
      * Test that second hostname works
    """
    route.add_hostname(second_hostname.hostname)

    response = client.get("/get")
    assert response.status_code == 200

    response = client2.get("/get")
    assert response.status_code == 200, "Adding host was not reconciled"

    route.remove_hostname(second_hostname.hostname)

    response = resilient_request("/get", http_client=client2, expected_status=404)
    assert response.status_code == 404, "Removing host was not reconciled"

    route.add_hostname(second_hostname.hostname)

    response = resilient_request("/get", http_client=client2)
    assert response.status_code == 200, "Adding host was not reconciled"

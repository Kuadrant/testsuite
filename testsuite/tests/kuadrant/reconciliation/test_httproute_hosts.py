"""Tests that HTTPRoute spec.hostnames changes are reconciled when changed."""
import pytest


@pytest.fixture
def second_route(proxy, blame):
    """Add a second hostname to a HTTPRoute"""
    return proxy.expose_hostname(blame("second"))


@pytest.fixture
def client2(second_route):
    """Client for a second hostname to HTTPRoute"""
    client = second_route.client()
    yield client
    client.close()


def test_add_host(client, client2, second_route, authorization, resilient_request):
    """
    Tests that HTTPRoute spec.hostnames changes are reconciled when changed:
      * Test that both hostnames work
      * Remove second hostname
      * Test that second hostname doesn't work
      * Add back second hostname
      * Test that second hostname works
    """

    response = client.get("/get")
    assert response.status_code == 200

    response = client2.get("/get")
    assert response.status_code == 200, "Adding host was not reconciled"

    authorization.remove_host(second_route.hostname)

    response = resilient_request("/get", http_client=client2, expected_status=404)
    assert response.status_code == 404, "Removing host was not reconciled"

    authorization.add_host(second_route.hostname)

    response = resilient_request("/get", http_client=client2)
    assert response.status_code == 200, "Adding host was not reconciled"

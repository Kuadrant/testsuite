"""Tests that HTTPRoute spec.hostnames changes are reconciled when changed."""

import pytest

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture
def second_hostname(exposer, gateway, blame):
    """Add a second hostname to a HTTPRoute"""
    return exposer.expose_hostname(blame("second"), gateway)


@pytest.fixture
def client2(second_hostname):
    """Client for a second hostname to HTTPRoute"""
    client = second_hostname.client(retry_codes={404})
    yield client
    client.close()


def test_add_host(client, client2, second_hostname, route):
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

    with second_hostname.client(retry_codes={200}) as failing_client:
        response = failing_client.get("/get")
        assert response.status_code == 404, "Removing host was not reconciled"

    route.add_hostname(second_hostname.hostname)

    response = client2.get("/get")
    assert response.status_code == 200, "Adding host was not reconciled"

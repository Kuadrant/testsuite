"""Conftest for multiple hosts tests"""
import pytest


@pytest.fixture(scope="module")
def second_hostname(exposer, gateway, blame):
    """Second exposed hostname"""
    return exposer.expose_hostname(blame("second"), gateway)


@pytest.fixture(scope="module")
def route(route, second_hostname):
    """Adds second host to the HTTPRoute"""
    route.add_hostname(second_hostname.hostname)
    return route


@pytest.fixture(scope="module")
def client2(second_hostname):
    """Client for second hostname"""
    client = second_hostname.client()
    yield client
    client.close()

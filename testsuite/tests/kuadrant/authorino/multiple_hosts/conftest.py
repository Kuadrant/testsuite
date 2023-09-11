"""Conftest for multiple hosts tests"""
import pytest


@pytest.fixture(scope="module")
def second_route(proxy, blame):
    """Second valid hostname"""
    return proxy.expose_hostname(blame("second"))


@pytest.fixture(scope="module")
def authorization(authorization, second_route):
    """Adds second host to the AuthConfig"""
    authorization.add_host(second_route.hostname)
    return authorization


@pytest.fixture(scope="module")
def client2(second_route):
    """Client for second hostname"""
    client = second_route.client()
    yield client
    client.close()

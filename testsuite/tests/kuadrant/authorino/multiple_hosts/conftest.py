"""Conftest for multiple hosts tests"""
import pytest

from testsuite.httpx import HttpxBackoffClient


@pytest.fixture(scope="module")
def hostname(envoy):
    """Original hostname"""
    return envoy.hostname


@pytest.fixture(scope="module")
def second_hostname(envoy, blame):
    """Second valid hostname"""
    return envoy.create_route(blame('second')).model.spec.host


@pytest.fixture(scope="module")
def authorization(authorization, second_hostname):
    """Adds second host to the AuthConfig"""
    authorization.add_host(second_hostname)
    return authorization


@pytest.fixture(scope="module")
def client2(second_hostname):
    """Client for second hostname"""
    client = HttpxBackoffClient(base_url=f"http://{second_hostname}")
    yield client
    client.close()

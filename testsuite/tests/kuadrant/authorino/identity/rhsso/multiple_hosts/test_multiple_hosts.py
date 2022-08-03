"""Tests AuthConfig with multiple specified hosts"""
import pytest

from testsuite.httpx import HttpxBackoffClient


@pytest.fixture(scope="module")
def authorization(authorization, second_hostname):
    """Adds second host to the AuthConfig"""
    authorization.add_host(second_hostname)
    return authorization


def test_original_host(client, auth):
    """Tests correct host"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200


def test_second_host(client, auth, second_hostname):
    """Tests correct host"""
    client = HttpxBackoffClient(base_url=f"http://{second_hostname}")
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

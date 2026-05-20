"""Test kubernetes token-review authorization with bound sa token that should contain host as audience by default"""

import pytest

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(authorization):
    """Add kubernetes token-review identity without any audiences"""
    authorization.identity.add_kubernetes("token-review-host")
    return authorization


@pytest.fixture(scope="module")
def audience(hostname):
    """Return hostname as only audience for the service account bound token"""
    return [hostname.hostname]


def test_host_audience(client, auth):
    """Test kubernetes token-review by adding hostname audience to the sa token and using it for the request"""
    response = client.get("/get")
    assert response.status_code == 401

    response = client.get("/get", auth=auth)
    assert response.status_code == 200

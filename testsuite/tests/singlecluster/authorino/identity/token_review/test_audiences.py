"""Test kubernetes token-review authorization with bound sa token that should contain all specified audiences"""

import pytest

pytestmark = [pytest.mark.authorino]


TEST_AUDIENCES = ["test-aud1", "test-aud2", "test-aud3"]


@pytest.fixture(scope="module")
def authorization(authorization):
    """Add kubernetes token-review identity with custom audiences specified"""
    authorization.identity.add_kubernetes("token-review-aud", TEST_AUDIENCES)
    return authorization


@pytest.fixture(scope="module")
def audience():
    """Return custom audiences for the service account bound token"""
    return TEST_AUDIENCES


def test_custom_audience(client, auth):
    """Test kubernetes token-review by adding custom audiences to the sa token and using it for the request"""
    response = client.get("/get")
    assert response.status_code == 401

    response = client.get("/get", auth=auth)
    assert response.status_code == 200

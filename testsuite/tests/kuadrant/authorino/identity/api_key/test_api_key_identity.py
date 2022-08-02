"""Tests authentication with API keys"""

import pytest

from testsuite.openshift.objects.api_key import APIKey


@pytest.fixture(scope="module")
def api_key_secret(openshift, blame):
    """Creates API Key Secret"""
    api_key = "test_api_key"
    secret = APIKey.create_instance(openshift, blame("api-key"), "api_label", api_key)
    secret.commit()
    yield secret, api_key
    secret.delete()


@pytest.fixture(scope="module")
def authorization(authorization):
    """Creates AuthConfig with API Key identity"""
    authorization.add_api_key_identity("api_key", "api_label")
    return authorization


def test_correct_auth(client, api_key_secret):
    """Tests request with correct API key"""
    _, key = api_key_secret
    response = client.get("/get", headers={"Authorization": f"APIKEY {key}"})
    assert response.status_code == 200


def test_no_auth(client):
    """Tests request with missing authorization header"""
    response = client.get("/get")
    assert response.status_code == 401


def test_wrong_auth(client):
    """Tests request with wrong API key"""
    response = client.get("/get", headers={"Authorization": "APIKEY invalid-key"})
    assert response.status_code == 401

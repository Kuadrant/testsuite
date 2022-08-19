"""Tests identity verification & authentication with API keys. Using selector.matchLabels"""
import pytest


@pytest.fixture(scope="module")
def authorization(authorization, module_label):
    """Creates AuthConfig with API key identity"""
    authorization.add_api_key_identity("api_key", match_label=module_label)
    return authorization


def test_correct_auth(client, api_key):
    """Tests request with correct API key"""
    response = client.get("/get", headers={"Authorization": f"APIKEY {api_key}"})
    assert response.status_code == 200


def test_no_auth(client):
    """Tests request with missing authorization header"""
    response = client.get("/get")
    assert response.status_code == 401


def test_invalid_api_key(client):
    """Tests request with wrong API key"""
    response = client.get("/get", headers={"Authorization": "APIKEY invalid-key"})
    assert response.status_code == 401


def test_invalid_api_key_secret(client, invalid_api_key):
    """Tests request that uses API key secret that is wrongly labeled"""
    response = client.get("/get", headers={"Authorization": f"APIKEY {invalid_api_key}"})
    assert response.status_code == 401

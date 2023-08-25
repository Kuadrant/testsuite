"""Tests identity verification & authentication with API keys. Using selector.matchLabels"""
import pytest


@pytest.fixture(scope="module")
def authorization(authorization, api_key):
    """Creates AuthConfig with API key identity"""
    authorization.identity.add_api_key("api_key", selector=api_key.selector)
    return authorization


def test_correct_auth(client, auth):
    """Tests request with correct API key"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200


def test_no_auth(client):
    """Tests request with missing authorization header"""
    response = client.get("/get")
    assert response.status_code == 401


def test_invalid_api_key(client):
    """Tests request with wrong invalid API key"""
    response = client.get("/get", headers={"Authorization": "APIKEY invalid_api_key_string"})
    assert response.status_code == 401


def test_invalid_api_key_secret(client, invalid_auth):
    """Tests request that uses API key secret that is wrongly labeled"""
    response = client.get("/get", auth=invalid_auth)
    assert response.status_code == 401

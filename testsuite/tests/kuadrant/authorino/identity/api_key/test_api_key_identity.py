"""Tests authentication with API keys"""

import pytest


@pytest.fixture(scope="module")
def label_selector():
    """Matching label for API key Secret and selector specified in spec.identity.apiKey.selector in the AuthConfig"""
    return "api_label"


@pytest.fixture(scope="module")
def mismatched_label_selector():
    """Label for API key secret that is different from the one specified in AuthConfig"""
    return "mismatched_api_label"


@pytest.fixture(scope="module")
def api_key_secret(create_api_key, label_selector):
    """Creates API key Secret"""
    api_key = "api_key_value"
    return create_api_key("api-key", label_selector, api_key), api_key


@pytest.fixture(scope="module")
def invalid_key_secret(create_api_key, mismatched_label_selector):
    """Creates API key Secret with label that does not match any of the labelSelectors defined by AuthConfig"""
    api_key = "invalid_secret_api_key_value"
    return create_api_key("mismatched-api-key", mismatched_label_selector, api_key), api_key


@pytest.fixture(scope="module")
def authorization(authorization, label_selector):
    """Creates AuthConfig with API key identity"""
    authorization.add_api_key_identity("api_key", label_selector)
    return authorization


def test_correct_auth(client, api_key_secret):
    """Tests request with correct API key"""
    _, api_key = api_key_secret
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


def test_invalid_api_key_secret(client, invalid_key_secret):
    """Tests request that uses API key secret that is wrongly labeled"""
    _, api_key = invalid_key_secret
    response = client.get("/get", headers={"Authorization": f"APIKEY {api_key}"})
    assert response.status_code == 401

"""Tests Secret reconciliation for API key identity verification & authentication"""
import pytest

from testsuite.httpx.auth import HeaderApiKeyAuth
from testsuite.objects import Selector


@pytest.fixture(scope="function")
def api_key(create_api_key, module_label):
    """Creates API key Secret"""
    return create_api_key("api-key", module_label, "api_key_value")


@pytest.fixture(scope="function")
def auth(api_key):
    """Valid API Key Auth"""
    return HeaderApiKeyAuth(api_key)


@pytest.fixture(scope="module")
def authorization(authorization, module_label):
    """Creates AuthConfig with API key identity"""
    authorization.identity.add_api_key("api_key", selector=Selector(matchLabels={"group": module_label}))
    return authorization


def test_create_new_api_key(client, create_api_key, module_label):
    """Test reconciliation when API key Secret is freshly created with valid label"""
    api_key = create_api_key("api-key", module_label, "new_api_key")
    auth = HeaderApiKeyAuth(api_key)
    response = client.get("/get", auth=auth)
    assert response.status_code == 200


def test_delete_api_key(client, auth, api_key):
    """Test reconciliation when API key Secret is deleted"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    api_key.delete()
    response = client.get("/get", auth=auth)
    assert response.status_code == 401


def test_update_api_key(client, auth, api_key):
    """Test reconciliation when API key Secret is updated"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    api_key.update_api_key("update_api_key")
    response = client.get("/get", auth=auth)
    assert response.status_code == 401

    auth = HeaderApiKeyAuth(api_key)
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

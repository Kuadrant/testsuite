"""
Tests for API key identity for AuthConfig configured with all_namespaces=true for cluster-wide
API key secret placement.
"""
import pytest

from testsuite.httpx.auth import HeaderApiKeyAuth


@pytest.fixture(scope="module")
def api_key(create_api_key, module_label, openshift2):
    """Creates API key Secret"""
    api_key = "cluster_wide_api_key"
    return create_api_key("wide-api-key", module_label, api_key, openshift2)


@pytest.fixture(scope="module")
def auth(api_key):
    """Valid API Key Auth"""
    return HeaderApiKeyAuth(api_key)


@pytest.fixture(scope="module")
def invalid_label_selector():
    """Label for API key secret that is different from the one specified in AuthConfig"""
    return "invalid_api_label"


@pytest.fixture(scope="module")
def invalid_api_key(create_api_key, invalid_label_selector, openshift2):
    """Creates API key Secret with label that does not match any of the labelSelectors defined by AuthConfig"""
    return create_api_key("invalid-api-key", invalid_label_selector, "invalid_api_key", openshift2)


@pytest.fixture(scope="module")
def invalid_auth(invalid_api_key):
    """Invalid key Auth"""
    return HeaderApiKeyAuth(invalid_api_key)


@pytest.fixture(scope="module")
def authorization(authorization, api_key):
    """Creates AuthConfig with API key identity"""
    authorization.identity.add_api_key("api_key", all_namespaces=True, selector=api_key.selector)
    return authorization


def test_correct_auth(client, auth):
    """Tests request with correct API key"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200


def test_invalid_api_key(client, invalid_auth):
    """Tests request with wrong API key"""
    response = client.get("/get", auth=invalid_auth)
    assert response.status_code == 401

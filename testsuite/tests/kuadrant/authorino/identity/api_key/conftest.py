"""Conftest for authorino API key identity"""
import pytest

from testsuite.httpx.auth import HeaderApiKeyAuth


@pytest.fixture(scope="module")
def invalid_label_selector():
    """Label for API key secret that is different from the one specified in AuthConfig"""
    return "invalid_api_label"


@pytest.fixture(scope="module")
def api_key(create_api_key, module_label):
    """Creates API key Secret"""
    api_key = "api_key_value"
    create_api_key("api-key", module_label, api_key)
    return api_key


@pytest.fixture(scope="module")
def auth(api_key):
    """Valid API Key Auth"""
    return HeaderApiKeyAuth(api_key)


@pytest.fixture(scope="module")
def invalid_api_key(create_api_key, invalid_label_selector):
    """Creates API key Secret with label that does not match any of the labelSelectors defined by AuthConfig"""
    api_key = "invalid_api_key"
    create_api_key("invalid-api-key", invalid_label_selector, api_key)
    return api_key


@pytest.fixture(scope="module")
def invalid_auth(invalid_api_key):
    """Invalid key Auth"""
    return HeaderApiKeyAuth(invalid_api_key)
